/*
 * KOS Virtual Filesystem C++ Implementation
 */

#include "vfs_api.h"
#include "vfs_core.hpp"
#include <cstring>
#include <cstdlib>
#include <memory>
#include <unordered_map>
#include <mutex>
#include <stdexcept>

namespace kos {
namespace vfs {

// Thread-local error storage
thread_local int g_vfs_errno = VFS_SUCCESS;

// Global VFS instance
static std::unique_ptr<VirtualFileSystem> g_vfs;
static std::mutex g_vfs_mutex;

// Handle management
static std::unordered_map<int, std::unique_ptr<FileHandle>> g_handles;
static int g_next_fd = 3; // Start after stdin/stdout/stderr
static std::mutex g_handle_mutex;

// Convert C++ exceptions to error codes
template<typename Func>
int safe_call(Func&& func) {
    try {
        func();
        g_vfs_errno = VFS_SUCCESS;
        return VFS_SUCCESS;
    } catch (const FileNotFoundError&) {
        g_vfs_errno = VFS_ENOENT;
        return VFS_ENOENT;
    } catch (const PermissionError&) {
        g_vfs_errno = VFS_EACCES;
        return VFS_EACCES;
    } catch (const FileExistsError&) {
        g_vfs_errno = VFS_EEXIST;
        return VFS_EEXIST;
    } catch (const NotDirectoryError&) {
        g_vfs_errno = VFS_ENOTDIR;
        return VFS_ENOTDIR;
    } catch (const IsDirectoryError&) {
        g_vfs_errno = VFS_EISDIR;
        return VFS_EISDIR;
    } catch (const std::bad_alloc&) {
        g_vfs_errno = VFS_ENOMEM;
        return VFS_ENOMEM;
    } catch (const std::invalid_argument& e) {
        g_vfs_errno = VFS_EINVAL;
        return VFS_EINVAL;
    } catch (...) {
        g_vfs_errno = VFS_ERROR;
        return VFS_ERROR;
    }
}

// Convert C++ exceptions to error codes with return value
template<typename T, typename Func>
T* safe_call_ptr(Func&& func) {
    try {
        T* result = func();
        g_vfs_errno = VFS_SUCCESS;
        return result;
    } catch (const FileNotFoundError&) {
        g_vfs_errno = VFS_ENOENT;
        return nullptr;
    } catch (const PermissionError&) {
        g_vfs_errno = VFS_EACCES;
        return nullptr;
    } catch (const FileExistsError&) {
        g_vfs_errno = VFS_EEXIST;
        return nullptr;
    } catch (const NotDirectoryError&) {
        g_vfs_errno = VFS_ENOTDIR;
        return nullptr;
    } catch (const IsDirectoryError&) {
        g_vfs_errno = VFS_EISDIR;
        return nullptr;
    } catch (const std::bad_alloc&) {
        g_vfs_errno = VFS_ENOMEM;
        return nullptr;
    } catch (const std::invalid_argument& e) {
        g_vfs_errno = VFS_EINVAL;
        return nullptr;
    } catch (...) {
        g_vfs_errno = VFS_ERROR;
        return nullptr;
    }
}

} // namespace vfs
} // namespace kos

extern "C" {

/* Initialize VFS subsystem */
int vfs_init(void) {
    std::lock_guard<std::mutex> lock(kos::vfs::g_vfs_mutex);
    
    if (kos::vfs::g_vfs) {
        return VFS_SUCCESS; // Already initialized
    }
    
    try {
        kos::vfs::g_vfs = std::make_unique<kos::vfs::VirtualFileSystem>();
        
        // Create standard directories
        auto root_ctx = vfs_context_create(0, 0);
        vfs_mkdir("/etc", 0755, root_ctx);
        vfs_mkdir("/var", 0755, root_ctx);
        vfs_mkdir("/var/lib", 0755, root_ctx);
        vfs_mkdir("/var/lib/kos", 0755, root_ctx);
        vfs_mkdir("/var/lib/kos/history", 0700, root_ctx);
        vfs_mkdir("/tmp", 01777, root_ctx);
        vfs_mkdir("/home", 0755, root_ctx);
        vfs_mkdir("/dev", 0755, root_ctx);
        vfs_mkdir("/proc", 0555, root_ctx);
        vfs_mkdir("/sys", 0555, root_ctx);
        vfs_context_destroy(root_ctx);
        
        return VFS_SUCCESS;
    } catch (...) {
        return VFS_ERROR;
    }
}

/* Shutdown VFS subsystem */
int vfs_shutdown(void) {
    std::lock_guard<std::mutex> lock(kos::vfs::g_vfs_mutex);
    
    // Close all open handles
    {
        std::lock_guard<std::mutex> handle_lock(kos::vfs::g_handle_mutex);
        kos::vfs::g_handles.clear();
    }
    
    kos::vfs::g_vfs.reset();
    return VFS_SUCCESS;
}

/* File operations */
vfs_handle_t* vfs_open(const char* path, int flags, mode_t mode, vfs_context_t* ctx) {
    if (!path || !kos::vfs::g_vfs) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return nullptr;
    }
    
    return kos::vfs::safe_call_ptr<vfs_handle_t>([&]() -> vfs_handle_t* {
        auto handle = kos::vfs::g_vfs->open(path, flags, mode, 
                                           ctx ? ctx->uid : 0, 
                                           ctx ? ctx->gid : 0);
        
        std::lock_guard<std::mutex> lock(kos::vfs::g_handle_mutex);
        int fd = kos::vfs::g_next_fd++;
        kos::vfs::g_handles[fd] = std::move(handle);
        
        auto* vfs_handle = new vfs_handle_t;
        vfs_handle->fd = fd;
        vfs_handle->private_data = nullptr;
        return vfs_handle;
    });
}

int vfs_close(vfs_handle_t* handle) {
    if (!handle) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        std::lock_guard<std::mutex> lock(kos::vfs::g_handle_mutex);
        kos::vfs::g_handles.erase(handle->fd);
        delete handle;
    });
}

ssize_t vfs_read(vfs_handle_t* handle, void* buffer, size_t size) {
    if (!handle || !buffer) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    std::lock_guard<std::mutex> lock(kos::vfs::g_handle_mutex);
    auto it = kos::vfs::g_handles.find(handle->fd);
    if (it == kos::vfs::g_handles.end()) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    try {
        auto data = it->second->read(size);
        std::memcpy(buffer, data.data(), data.size());
        return data.size();
    } catch (...) {
        kos::vfs::g_vfs_errno = VFS_ERROR;
        return -1;
    }
}

ssize_t vfs_write(vfs_handle_t* handle, const void* buffer, size_t size) {
    if (!handle || !buffer) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    std::lock_guard<std::mutex> lock(kos::vfs::g_handle_mutex);
    auto it = kos::vfs::g_handles.find(handle->fd);
    if (it == kos::vfs::g_handles.end()) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    try {
        std::vector<uint8_t> data(static_cast<const uint8_t*>(buffer), 
                                  static_cast<const uint8_t*>(buffer) + size);
        return it->second->write(data);
    } catch (...) {
        kos::vfs::g_vfs_errno = VFS_ERROR;
        return -1;
    }
}

off_t vfs_lseek(vfs_handle_t* handle, off_t offset, int whence) {
    if (!handle) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    std::lock_guard<std::mutex> lock(kos::vfs::g_handle_mutex);
    auto it = kos::vfs::g_handles.find(handle->fd);
    if (it == kos::vfs::g_handles.end()) {
        kos::vfs::g_vfs_errno = VFS_EINVAL;
        return -1;
    }
    
    try {
        return it->second->seek(offset, whence);
    } catch (...) {
        kos::vfs::g_vfs_errno = VFS_ERROR;
        return -1;
    }
}

/* Directory operations */
int vfs_mkdir(const char* path, mode_t mode, vfs_context_t* ctx) {
    if (!path || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        kos::vfs::g_vfs->mkdir(path, mode, ctx ? ctx->uid : 0, ctx ? ctx->gid : 0);
    });
}

int vfs_rmdir(const char* path, vfs_context_t* ctx) {
    if (!path || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        kos::vfs::g_vfs->rmdir(path, ctx ? ctx->uid : 0);
    });
}

/* Path operations */
int vfs_stat(const char* path, vfs_stat_t* stat, vfs_context_t* ctx) {
    if (!path || !stat || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        auto info = kos::vfs::g_vfs->stat(path, ctx ? ctx->uid : 0);
        
        stat->st_dev = 0;
        stat->st_ino = info.inode;
        stat->st_mode = info.mode;
        stat->st_nlink = 1;
        stat->st_uid = info.uid;
        stat->st_gid = info.gid;
        stat->st_size = info.size;
        stat->st_atime_sec = info.atime;
        stat->st_mtime_sec = info.mtime;
        stat->st_ctime_sec = info.ctime;
        stat->st_blksize = 4096;
        stat->st_blocks = (info.size + 511) / 512;
    });
}

int vfs_access(const char* path, int mode, vfs_context_t* ctx) {
    if (!path || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        kos::vfs::g_vfs->access(path, mode, ctx ? ctx->uid : 0);
    });
}

int vfs_unlink(const char* path, vfs_context_t* ctx) {
    if (!path || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        kos::vfs::g_vfs->unlink(path, ctx ? ctx->uid : 0);
    });
}

int vfs_rename(const char* oldpath, const char* newpath, vfs_context_t* ctx) {
    if (!oldpath || !newpath || !kos::vfs::g_vfs) {
        return VFS_EINVAL;
    }
    
    return kos::vfs::safe_call([&]() {
        kos::vfs::g_vfs->rename(oldpath, newpath, ctx ? ctx->uid : 0);
    });
}

/* Context management */
vfs_context_t* vfs_context_create(uid_t uid, gid_t gid) {
    auto* ctx = new vfs_context_t;
    ctx->uid = uid;
    ctx->gid = gid;
    ctx->umask = 022;
    ctx->cwd = strdup("/");
    return ctx;
}

void vfs_context_destroy(vfs_context_t* ctx) {
    if (ctx) {
        free(ctx->cwd);
        delete ctx;
    }
}

int vfs_context_set_cwd(vfs_context_t* ctx, const char* path) {
    if (!ctx || !path) {
        return VFS_EINVAL;
    }
    
    // Verify path exists and is a directory
    vfs_stat_t stat;
    if (vfs_stat(path, &stat, ctx) != VFS_SUCCESS) {
        return vfs_errno();
    }
    
    if (!(stat.st_mode & S_IFDIR)) {
        kos::vfs::g_vfs_errno = VFS_ENOTDIR;
        return VFS_ENOTDIR;
    }
    
    free(ctx->cwd);
    ctx->cwd = strdup(path);
    return VFS_SUCCESS;
}

const char* vfs_context_get_cwd(vfs_context_t* ctx) {
    return ctx ? ctx->cwd : "/";
}

/* Error handling */
const char* vfs_strerror(int error) {
    switch (error) {
        case VFS_SUCCESS: return "Success";
        case VFS_ERROR: return "General error";
        case VFS_ENOENT: return "No such file or directory";
        case VFS_EACCES: return "Permission denied";
        case VFS_EEXIST: return "File exists";
        case VFS_ENOTDIR: return "Not a directory";
        case VFS_EISDIR: return "Is a directory";
        case VFS_ENOMEM: return "Out of memory";
        case VFS_ENOSPC: return "No space left";
        case VFS_EINVAL: return "Invalid argument";
        case VFS_EBUSY: return "Resource busy";
        default: return "Unknown error";
    }
}

int vfs_errno(void) {
    return kos::vfs::g_vfs_errno;
}

} // extern "C"