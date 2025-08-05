/*
 * KOS Virtual Filesystem Core Implementation
 */

#include "vfs_core.hpp"
#include <algorithm>
#include <sstream>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>

namespace kos {
namespace vfs {

// Static inode counter
uint64_t VNode::next_inode = 1;

// VNode implementation
VNode::VNode(const std::string& name, Type type, uint16_t mode, 
             uint32_t uid, uint32_t gid)
    : name(name), type(type), inode(next_inode++), mode(mode),
      uid(uid), gid(gid), size(0) {
    auto now = std::chrono::system_clock::now();
    atime = mtime = ctime = now;
}

uint64_t VNode::getSize() const {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type == FILE) {
        return data.size();
    } else if (type == DIRECTORY) {
        return children.size() * 64; // Approximate
    } else if (type == SYMLINK) {
        return target.size();
    }
    return 0;
}

std::vector<uint8_t> VNode::read(size_t offset, size_t size) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != FILE) {
        throw IsDirectoryError(name);
    }
    
    updateAccessTime();
    
    if (offset >= data.size()) {
        return std::vector<uint8_t>();
    }
    
    size_t read_size = std::min(size, data.size() - offset);
    return std::vector<uint8_t>(data.begin() + offset, 
                                data.begin() + offset + read_size);
}

size_t VNode::write(const std::vector<uint8_t>& write_data, size_t offset) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != FILE) {
        throw IsDirectoryError(name);
    }
    
    // Extend file if necessary
    if (offset + write_data.size() > data.size()) {
        data.resize(offset + write_data.size());
    }
    
    // Copy data
    std::copy(write_data.begin(), write_data.end(), data.begin() + offset);
    
    updateModifyTime();
    return write_data.size();
}

void VNode::truncate(size_t new_size) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != FILE) {
        throw IsDirectoryError(name);
    }
    
    data.resize(new_size);
    updateModifyTime();
}

void VNode::addChild(const std::string& child_name, std::shared_ptr<VNode> child) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != DIRECTORY) {
        throw NotDirectoryError(name);
    }
    
    if (children.find(child_name) != children.end()) {
        throw FileExistsError(name + "/" + child_name);
    }
    
    children[child_name] = child;
    child->parent = shared_from_this();
    updateModifyTime();
}

void VNode::removeChild(const std::string& child_name) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != DIRECTORY) {
        throw NotDirectoryError(name);
    }
    
    auto it = children.find(child_name);
    if (it == children.end()) {
        throw FileNotFoundError(child_name);
    }
    
    children.erase(it);
    updateModifyTime();
}

std::shared_ptr<VNode> VNode::getChild(const std::string& child_name) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != DIRECTORY) {
        throw NotDirectoryError(name);
    }
    
    auto it = children.find(child_name);
    if (it == children.end()) {
        return nullptr;
    }
    
    return it->second;
}

std::vector<DirEntry> VNode::listChildren() {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    if (type != DIRECTORY) {
        throw NotDirectoryError(name);
    }
    
    std::vector<DirEntry> entries;
    
    // Add . and ..
    entries.push_back({".", inode, DT_DIR});
    if (auto p = parent.lock()) {
        entries.push_back({"..", p->inode, DT_DIR});
    } else {
        entries.push_back({"..", inode, DT_DIR}); // Root's parent is itself
    }
    
    // Add children
    for (const auto& [name, child] : children) {
        uint8_t dtype = DT_UNKNOWN;
        switch (child->type) {
            case FILE: dtype = DT_REG; break;
            case DIRECTORY: dtype = DT_DIR; break;
            case SYMLINK: dtype = DT_LNK; break;
            case DEVICE: dtype = DT_CHR; break;
            case PIPE: dtype = DT_FIFO; break;
            case SOCKET: dtype = DT_SOCK; break;
        }
        entries.push_back({name, child->inode, dtype});
    }
    
    updateAccessTime();
    return entries;
}

bool VNode::canRead(uint32_t check_uid, uint32_t check_gid) const {
    if (check_uid == 0) return true; // Root can read anything
    
    if (check_uid == uid) {
        return mode & S_IRUSR;
    } else if (check_gid == gid) {
        return mode & S_IRGRP;
    } else {
        return mode & S_IROTH;
    }
}

bool VNode::canWrite(uint32_t check_uid, uint32_t check_gid) const {
    if (check_uid == 0) return true; // Root can write anything
    
    if (check_uid == uid) {
        return mode & S_IWUSR;
    } else if (check_gid == gid) {
        return mode & S_IWGRP;
    } else {
        return mode & S_IWOTH;
    }
}

bool VNode::canExecute(uint32_t check_uid, uint32_t check_gid) const {
    if (check_uid == 0) return true; // Root can execute anything
    
    if (check_uid == uid) {
        return mode & S_IXUSR;
    } else if (check_gid == gid) {
        return mode & S_IXGRP;
    } else {
        return mode & S_IXOTH;
    }
}

void VNode::chmod(uint16_t new_mode) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    mode = new_mode;
    ctime = std::chrono::system_clock::now();
}

void VNode::chown(uint32_t new_uid, uint32_t new_gid) {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    uid = new_uid;
    gid = new_gid;
    ctime = std::chrono::system_clock::now();
}

void VNode::updateAccessTime() {
    atime = std::chrono::system_clock::now();
}

void VNode::updateModifyTime() {
    auto now = std::chrono::system_clock::now();
    mtime = now;
    ctime = now;
}

FileInfo VNode::getInfo() const {
    std::lock_guard<std::recursive_mutex> lock(mutex);
    
    FileInfo info;
    info.inode = inode;
    info.mode = mode;
    
    // Set file type bits
    switch (type) {
        case FILE: info.mode |= S_IFREG; break;
        case DIRECTORY: info.mode |= S_IFDIR; break;
        case SYMLINK: info.mode |= S_IFLNK; break;
        case DEVICE: info.mode |= S_IFCHR; break;
        case PIPE: info.mode |= S_IFIFO; break;
        case SOCKET: info.mode |= S_IFSOCK; break;
    }
    
    info.uid = uid;
    info.gid = gid;
    info.size = getSize();
    
    auto time_to_unix = [](const std::chrono::system_clock::time_point& tp) {
        return std::chrono::duration_cast<std::chrono::seconds>(
            tp.time_since_epoch()).count();
    };
    
    info.atime = time_to_unix(atime);
    info.mtime = time_to_unix(mtime);
    info.ctime = time_to_unix(ctime);
    info.nlink = 1;
    info.dev = 0;
    info.rdev = 0;
    
    return info;
}

// FileHandle implementation
FileHandle::FileHandle(std::shared_ptr<VNode> vnode, int flags, 
                       uint32_t uid, uint32_t gid)
    : vnode(vnode), flags(flags), position(0), uid(uid), gid(gid) {
    
    // Check permissions
    if ((flags & O_RDONLY || flags & O_RDWR) && !vnode->canRead(uid, gid)) {
        throw PermissionError("Read permission denied");
    }
    
    if ((flags & O_WRONLY || flags & O_RDWR) && !vnode->canWrite(uid, gid)) {
        throw PermissionError("Write permission denied");
    }
    
    // Handle O_TRUNC
    if ((flags & O_TRUNC) && (flags & O_WRONLY || flags & O_RDWR)) {
        vnode->truncate(0);
    }
    
    // Handle O_APPEND
    if (flags & O_APPEND) {
        position = vnode->getSize();
    }
}

std::vector<uint8_t> FileHandle::read(size_t size) {
    if (!canRead()) {
        throw PermissionError("File not opened for reading");
    }
    
    auto data = vnode->read(position, size);
    position += data.size();
    return data;
}

size_t FileHandle::write(const std::vector<uint8_t>& data) {
    if (!canWrite()) {
        throw PermissionError("File not opened for writing");
    }
    
    size_t written = vnode->write(data, position);
    position += written;
    return written;
}

off_t FileHandle::seek(off_t offset, int whence) {
    switch (whence) {
        case SEEK_SET:
            position = offset;
            break;
        case SEEK_CUR:
            position += offset;
            break;
        case SEEK_END:
            position = vnode->getSize() + offset;
            break;
        default:
            throw std::invalid_argument("Invalid whence");
    }
    
    // Clamp to valid range
    if (position < 0) position = 0;
    
    return position;
}

void FileHandle::truncate(size_t size) {
    if (!canWrite()) {
        throw PermissionError("File not opened for writing");
    }
    
    vnode->truncate(size);
}

FileInfo FileHandle::stat() {
    return vnode->getInfo();
}

bool FileHandle::canRead() const {
    return (flags & O_RDONLY) || (flags & O_RDWR);
}

bool FileHandle::canWrite() const {
    return (flags & O_WRONLY) || (flags & O_RDWR);
}

// RamFS implementation
RamFS::RamFS(bool readonly) : readonly(readonly) {
    root = std::make_shared<VNode>("/", VNode::DIRECTORY, 0755, 0, 0);
}

// VirtualFileSystem implementation
VirtualFileSystem::VirtualFileSystem() {
    rootfs = std::make_shared<RamFS>();
}

std::shared_ptr<VNode> VirtualFileSystem::resolvePath(const std::string& path, 
                                                      uint32_t uid,
                                                      bool follow_symlinks) {
    auto parts = splitPath(normalizePath(path));
    auto current = rootfs->getRoot();
    
    for (size_t i = 0; i < parts.size(); ++i) {
        const auto& part = parts[i];
        
        if (!current->canExecute(uid, 0)) {
            throw PermissionError("Permission denied");
        }
        
        auto child = current->getChild(part);
        if (!child) {
            throw FileNotFoundError(path);
        }
        
        // Handle symlinks
        if (follow_symlinks && child->getType() == VNode::SYMLINK) {
            // Recursive resolution
            auto target = child->getTarget();
            if (target[0] == '/') {
                // Absolute symlink
                child = resolvePath(target, uid, follow_symlinks);
            } else {
                // Relative symlink
                std::string base = "/";
                for (size_t j = 0; j < i; ++j) {
                    base += parts[j] + "/";
                }
                child = resolvePath(base + target, uid, follow_symlinks);
            }
        }
        
        current = child;
    }
    
    return current;
}

std::pair<std::shared_ptr<VNode>, std::string> 
VirtualFileSystem::resolveParent(const std::string& path, uint32_t uid) {
    auto normalized = normalizePath(path);
    auto last_slash = normalized.rfind('/');
    
    if (last_slash == 0) {
        // Parent is root
        return {rootfs->getRoot(), normalized.substr(1)};
    }
    
    auto parent_path = normalized.substr(0, last_slash);
    auto filename = normalized.substr(last_slash + 1);
    
    auto parent = resolvePath(parent_path, uid);
    return {parent, filename};
}

std::string VirtualFileSystem::normalizePath(const std::string& path) {
    if (path.empty() || path[0] != '/') {
        throw std::invalid_argument("Path must be absolute");
    }
    
    std::vector<std::string> parts;
    std::stringstream ss(path);
    std::string part;
    
    while (std::getline(ss, part, '/')) {
        if (part.empty() || part == ".") {
            continue;
        } else if (part == "..") {
            if (!parts.empty()) {
                parts.pop_back();
            }
        } else {
            parts.push_back(part);
        }
    }
    
    std::string result = "/";
    for (size_t i = 0; i < parts.size(); ++i) {
        result += parts[i];
        if (i < parts.size() - 1) {
            result += "/";
        }
    }
    
    return result.empty() ? "/" : result;
}

std::vector<std::string> VirtualFileSystem::splitPath(const std::string& path) {
    std::vector<std::string> parts;
    std::stringstream ss(path);
    std::string part;
    
    // Skip leading /
    std::getline(ss, part, '/');
    
    while (std::getline(ss, part, '/')) {
        if (!part.empty()) {
            parts.push_back(part);
        }
    }
    
    return parts;
}

std::unique_ptr<FileHandle> VirtualFileSystem::open(const std::string& path, 
                                                   int flags, mode_t mode,
                                                   uint32_t uid, uint32_t gid) {
    if (flags & O_CREAT) {
        try {
            auto existing = resolvePath(path, uid);
            if (flags & O_EXCL) {
                throw FileExistsError(path);
            }
            return std::make_unique<FileHandle>(existing, flags, uid, gid);
        } catch (const FileNotFoundError&) {
            // Create the file
            auto [parent, filename] = resolveParent(path, uid);
            
            if (!parent->canWrite(uid, gid)) {
                throw PermissionError("Cannot create file");
            }
            
            auto file = std::make_shared<VNode>(filename, VNode::FILE, 
                                               mode & ~022, uid, gid);
            parent->addChild(filename, file);
            return std::make_unique<FileHandle>(file, flags, uid, gid);
        }
    } else {
        auto vnode = resolvePath(path, uid);
        return std::make_unique<FileHandle>(vnode, flags, uid, gid);
    }
}

void VirtualFileSystem::mkdir(const std::string& path, mode_t mode, 
                             uint32_t uid, uint32_t gid) {
    auto [parent, dirname] = resolveParent(path, uid);
    
    if (!parent->canWrite(uid, gid)) {
        throw PermissionError("Cannot create directory");
    }
    
    auto dir = std::make_shared<VNode>(dirname, VNode::DIRECTORY, 
                                       mode & ~022, uid, gid);
    parent->addChild(dirname, dir);
}

void VirtualFileSystem::rmdir(const std::string& path, uint32_t uid) {
    auto [parent, dirname] = resolveParent(path, uid);
    
    if (!parent->canWrite(uid, 0)) {
        throw PermissionError("Cannot remove directory");
    }
    
    auto dir = parent->getChild(dirname);
    if (!dir || dir->getType() != VNode::DIRECTORY) {
        throw NotDirectoryError(path);
    }
    
    // Check if directory is empty
    auto entries = dir->listChildren();
    if (entries.size() > 2) { // More than . and ..
        throw std::runtime_error("Directory not empty");
    }
    
    parent->removeChild(dirname);
}

FileInfo VirtualFileSystem::stat(const std::string& path, uint32_t uid) {
    auto vnode = resolvePath(path, uid);
    return vnode->getInfo();
}

FileInfo VirtualFileSystem::lstat(const std::string& path, uint32_t uid) {
    auto vnode = resolvePath(path, uid, false); // Don't follow symlinks
    return vnode->getInfo();
}

void VirtualFileSystem::access(const std::string& path, int mode, uint32_t uid) {
    auto vnode = resolvePath(path, uid);
    
    if (mode & R_OK && !vnode->canRead(uid, 0)) {
        throw PermissionError("Read access denied");
    }
    
    if (mode & W_OK && !vnode->canWrite(uid, 0)) {
        throw PermissionError("Write access denied");
    }
    
    if (mode & X_OK && !vnode->canExecute(uid, 0)) {
        throw PermissionError("Execute access denied");
    }
}

void VirtualFileSystem::unlink(const std::string& path, uint32_t uid) {
    auto [parent, filename] = resolveParent(path, uid);
    
    if (!parent->canWrite(uid, 0)) {
        throw PermissionError("Cannot remove file");
    }
    
    auto file = parent->getChild(filename);
    if (!file) {
        throw FileNotFoundError(path);
    }
    
    if (file->getType() == VNode::DIRECTORY) {
        throw IsDirectoryError(path);
    }
    
    parent->removeChild(filename);
}

void VirtualFileSystem::rename(const std::string& oldpath, 
                              const std::string& newpath, uint32_t uid) {
    auto [old_parent, old_name] = resolveParent(oldpath, uid);
    auto [new_parent, new_name] = resolveParent(newpath, uid);
    
    if (!old_parent->canWrite(uid, 0) || !new_parent->canWrite(uid, 0)) {
        throw PermissionError("Cannot rename");
    }
    
    auto vnode = old_parent->getChild(old_name);
    if (!vnode) {
        throw FileNotFoundError(oldpath);
    }
    
    // Remove from old location
    old_parent->removeChild(old_name);
    
    // Add to new location
    try {
        new_parent->addChild(new_name, vnode);
    } catch (...) {
        // Restore on failure
        old_parent->addChild(old_name, vnode);
        throw;
    }
}

} // namespace vfs
} // namespace kos