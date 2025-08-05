/*
 * KOS Virtual Filesystem Core C++ Classes
 */

#ifndef KOS_VFS_CORE_HPP
#define KOS_VFS_CORE_HPP

#include <string>
#include <memory>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <mutex>
#include <sys/types.h>
#include <sys/stat.h>

namespace kos {
namespace vfs {

// Forward declarations
class VNode;
class FileSystem;
class FileHandle;

// Exceptions
class VFSException : public std::exception {
protected:
    std::string msg;
public:
    explicit VFSException(const std::string& message) : msg(message) {}
    const char* what() const noexcept override { return msg.c_str(); }
};

class FileNotFoundError : public VFSException {
public:
    explicit FileNotFoundError(const std::string& path) 
        : VFSException("File not found: " + path) {}
};

class PermissionError : public VFSException {
public:
    explicit PermissionError(const std::string& msg) 
        : VFSException("Permission denied: " + msg) {}
};

class FileExistsError : public VFSException {
public:
    explicit FileExistsError(const std::string& path) 
        : VFSException("File exists: " + path) {}
};

class NotDirectoryError : public VFSException {
public:
    explicit NotDirectoryError(const std::string& path) 
        : VFSException("Not a directory: " + path) {}
};

class IsDirectoryError : public VFSException {
public:
    explicit IsDirectoryError(const std::string& path) 
        : VFSException("Is a directory: " + path) {}
};

// File information
struct FileInfo {
    uint64_t inode;
    uint16_t mode;
    uint32_t uid;
    uint32_t gid;
    uint64_t size;
    uint64_t atime;
    uint64_t mtime;
    uint64_t ctime;
    uint32_t nlink;
    uint32_t dev;
    uint32_t rdev;
};

// File type constants for directory entries
#define DT_UNKNOWN  0
#define DT_FIFO     1
#define DT_CHR      2
#define DT_DIR      4
#define DT_BLK      6
#define DT_REG      8
#define DT_LNK      10
#define DT_SOCK     12
#define DT_WHT      14

// Directory entry
struct DirEntry {
    std::string name;
    uint64_t inode;
    uint8_t type;
    
    DirEntry() : name(""), inode(0), type(DT_UNKNOWN) {}
    DirEntry(const std::string& n, uint64_t i, uint8_t t) 
        : name(n), inode(i), type(t) {}
};

// VNode - Virtual node representing a file/directory
class VNode : public std::enable_shared_from_this<VNode> {
public:
    enum Type {
        FILE = 1,
        DIRECTORY = 2,
        SYMLINK = 3,
        DEVICE = 4,
        PIPE = 5,
        SOCKET = 6
    };

private:
    std::string name;
    Type type;
    uint64_t inode;
    uint16_t mode;
    uint32_t uid;
    uint32_t gid;
    uint64_t size;
    std::chrono::system_clock::time_point atime;
    std::chrono::system_clock::time_point mtime;
    std::chrono::system_clock::time_point ctime;
    
    // For files
    std::vector<uint8_t> data;
    
    // For directories
    std::unordered_map<std::string, std::shared_ptr<VNode>> children;
    std::weak_ptr<VNode> parent;
    
    // For symlinks
    std::string target;
    
    mutable std::recursive_mutex mutex;
    
    static uint64_t next_inode;

public:
    explicit VNode(const std::string& name, Type type, uint16_t mode, 
                   uint32_t uid, uint32_t gid);
    
    // Getters
    const std::string& getName() const { return name; }
    Type getType() const { return type; }
    uint64_t getInode() const { return inode; }
    uint16_t getMode() const { return mode; }
    uint32_t getUid() const { return uid; }
    uint32_t getGid() const { return gid; }
    uint64_t getSize() const;
    
    // File operations
    std::vector<uint8_t> read(size_t offset, size_t size);
    size_t write(const std::vector<uint8_t>& data, size_t offset);
    void truncate(size_t size);
    
    // Directory operations
    void addChild(const std::string& name, std::shared_ptr<VNode> child);
    void removeChild(const std::string& name);
    std::shared_ptr<VNode> getChild(const std::string& name);
    std::vector<DirEntry> listChildren();
    
    // Symlink operations
    void setTarget(const std::string& target) { this->target = target; }
    const std::string& getTarget() const { return target; }
    
    // Permission checks
    bool canRead(uint32_t uid, uint32_t gid) const;
    bool canWrite(uint32_t uid, uint32_t gid) const;
    bool canExecute(uint32_t uid, uint32_t gid) const;
    
    // Metadata operations
    void chmod(uint16_t mode);
    void chown(uint32_t uid, uint32_t gid);
    void updateAccessTime();
    void updateModifyTime();
    
    FileInfo getInfo() const;
};

// FileHandle - Open file handle
class FileHandle {
private:
    std::shared_ptr<VNode> vnode;
    int flags;
    size_t position;
    uint32_t uid;
    uint32_t gid;

public:
    FileHandle(std::shared_ptr<VNode> vnode, int flags, uint32_t uid, uint32_t gid);
    
    std::vector<uint8_t> read(size_t size);
    size_t write(const std::vector<uint8_t>& data);
    off_t seek(off_t offset, int whence);
    void truncate(size_t size);
    FileInfo stat();
    
    bool canRead() const;
    bool canWrite() const;
};

// FileSystem - Abstract base for different filesystem types
class FileSystem {
public:
    virtual ~FileSystem() = default;
    
    virtual std::shared_ptr<VNode> getRoot() = 0;
    virtual std::string getType() const = 0;
    virtual bool isReadOnly() const = 0;
};

// RamFS - In-memory filesystem
class RamFS : public FileSystem {
private:
    std::shared_ptr<VNode> root;
    bool readonly;

public:
    explicit RamFS(bool readonly = false);
    
    std::shared_ptr<VNode> getRoot() override { return root; }
    std::string getType() const override { return "ramfs"; }
    bool isReadOnly() const override { return readonly; }
};

// VirtualFileSystem - Main VFS class
class VirtualFileSystem {
private:
    struct Mount {
        std::string path;
        std::shared_ptr<FileSystem> fs;
        std::shared_ptr<VNode> mountpoint;
    };
    
    std::shared_ptr<FileSystem> rootfs;
    std::vector<Mount> mounts;
    mutable std::mutex mount_mutex;
    
    // Path resolution
    std::shared_ptr<VNode> resolvePath(const std::string& path, uint32_t uid,
                                      bool follow_symlinks = true);
    std::pair<std::shared_ptr<VNode>, std::string> resolveParent(const std::string& path, 
                                                                  uint32_t uid);
    std::string normalizePath(const std::string& path);
    std::vector<std::string> splitPath(const std::string& path);

public:
    VirtualFileSystem();
    
    // File operations
    std::unique_ptr<FileHandle> open(const std::string& path, int flags, 
                                     mode_t mode, uint32_t uid, uint32_t gid);
    
    // Directory operations
    void mkdir(const std::string& path, mode_t mode, uint32_t uid, uint32_t gid);
    void rmdir(const std::string& path, uint32_t uid);
    std::vector<DirEntry> readdir(const std::string& path, uint32_t uid);
    
    // Path operations
    FileInfo stat(const std::string& path, uint32_t uid);
    FileInfo lstat(const std::string& path, uint32_t uid);
    void access(const std::string& path, int mode, uint32_t uid);
    void chmod(const std::string& path, mode_t mode, uint32_t uid);
    void chown(const std::string& path, uid_t owner, gid_t group, uint32_t uid);
    void unlink(const std::string& path, uint32_t uid);
    void rename(const std::string& oldpath, const std::string& newpath, uint32_t uid);
    void link(const std::string& oldpath, const std::string& newpath, uint32_t uid);
    void symlink(const std::string& target, const std::string& linkpath, uint32_t uid);
    std::string readlink(const std::string& path, uint32_t uid);
    
    // Mount operations
    void mount(const std::string& source, const std::string& target,
               const std::string& fstype, unsigned long flags, 
               const void* data, uint32_t uid);
    void umount(const std::string& target, uint32_t uid);
    
    // Utility
    std::string realpath(const std::string& path, uint32_t uid);
};

} // namespace vfs
} // namespace kos

#endif // KOS_VFS_CORE_HPP