/*
 * KAIM C++ Library Header
 */

#ifndef KAIM_LIB_H
#define KAIM_LIB_H

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <unistd.h>

// ioctl definitions matching kernel module
#define KAIM_IOCTL_MAGIC 'K'

struct kaim_elevate_req {
    pid_t target_pid;
    uint32_t flags;
    uint32_t duration;
};

struct kaim_status {
    char version[32];
    uint32_t process_count;
    uint32_t device_count;
    uint64_t elevations;
    uint64_t device_opens;
    uint64_t permission_checks;
    uint64_t denials;
};

struct kaim_device_req {
    char device[64];
    char mode[4];
    int fd;
};

struct kaim_perm_check {
    pid_t pid;
    uint32_t flag;
    int result;
};

struct kaim_perm_drop {
    pid_t pid;
    uint32_t flag;
};

struct kaim_audit_req {
    uint32_t count;
    char buffer[4096];
};

#define KAIM_IOCTL_ELEVATE    _IOW(KAIM_IOCTL_MAGIC, 1, struct kaim_elevate_req)
#define KAIM_IOCTL_STATUS     _IOR(KAIM_IOCTL_MAGIC, 2, struct kaim_status)
#define KAIM_IOCTL_SESSION    _IOW(KAIM_IOCTL_MAGIC, 3, void*)
#define KAIM_IOCTL_DEVICE     _IOWR(KAIM_IOCTL_MAGIC, 4, struct kaim_device_req)
#define KAIM_IOCTL_CHECK_PERM _IOR(KAIM_IOCTL_MAGIC, 5, struct kaim_perm_check)
#define KAIM_IOCTL_DROP_PERM  _IOW(KAIM_IOCTL_MAGIC, 6, struct kaim_perm_drop)
#define KAIM_IOCTL_AUDIT      _IOR(KAIM_IOCTL_MAGIC, 7, struct kaim_audit_req)

#define KAIM_SOCKET_PATH "/var/run/kaim.sock"

namespace KAIM {

class KAIMClientImpl;

/**
 * Main KAIM client class for C++ applications
 */
class KAIMClient {
public:
    /**
     * Create KAIM client
     * @param app_name Application name
     * @param fingerprint Application fingerprint for authentication
     */
    KAIMClient(const std::string& app_name, const std::string& fingerprint);
    ~KAIMClient();
    
    /**
     * Connect to KAIM daemon
     * @return true on success, false on failure
     */
    bool connect();
    
    /**
     * Disconnect from KAIM daemon
     */
    void disconnect();
    
    /**
     * Open a device with permission checks
     * @param device Device name (e.g., "sda", "eth0")
     * @param mode Access mode ("r", "w", "rw")
     * @return File descriptor on success, -1 on failure
     */
    int deviceOpen(const std::string& device, const std::string& mode = "r");
    
    /**
     * Control a device
     * @param device Device name
     * @param command Control command
     * @param params Command parameters
     * @return Result map with "success" key and command-specific data
     */
    std::map<std::string, std::string> deviceControl(
        const std::string& device,
        const std::string& command,
        const std::map<std::string, std::string>& params = {}
    );
    
    /**
     * Request privilege elevation
     * @param pid Process ID to elevate (0 for current process)
     * @param flags Permission flags to request
     * @return true on success, false on failure
     */
    bool processElevate(pid_t pid = 0, 
                       const std::vector<std::string>& flags = {});
    
    /**
     * Get KAIM daemon status
     * @return Status information map
     */
    std::map<std::string, std::string> getStatus();
    
    /**
     * Check if we have a specific permission
     * @param flag Permission flag name
     * @return true if permission granted, false otherwise
     */
    bool checkPermission(const std::string& flag);
    
    /**
     * List all granted permissions
     * @return Vector of permission flag names
     */
    std::vector<std::string> listPermissions();
    
    /**
     * Get last error message
     * @return Error description
     */
    std::string getLastError() const;
    
private:
    std::unique_ptr<KAIMClientImpl> impl_;
};

} // namespace KAIM

// C API for compatibility
extern "C" {

/**
 * Initialize KAIM client
 * @param app_name Application name
 * @param fingerprint Application fingerprint
 * @return 1 on success, 0 on failure
 */
int kaim_init(const char* app_name, const char* fingerprint);

/**
 * Cleanup KAIM client
 */
void kaim_cleanup();

/**
 * Open device
 * @param device Device name
 * @param mode Access mode
 * @return File descriptor or -1
 */
int kaim_device_open(const char* device, const char* mode);

/**
 * Control device
 * @param device Device name
 * @param command Control command
 * @param params_json Parameters in JSON format (can be NULL)
 * @param result_json Buffer for result JSON
 * @param result_size Size of result buffer
 * @return 1 on success, 0 on failure
 */
int kaim_device_control(const char* device, const char* command,
                       const char* params_json, char* result_json, int result_size);

/**
 * Elevate process privileges
 * @param pid Process ID (0 for current)
 * @param flags Array of flag names
 * @param flag_count Number of flags
 * @return 1 on success, 0 on failure
 */
int kaim_process_elevate(pid_t pid, const char** flags, int flag_count);

/**
 * Get status
 * @param status_json Buffer for status JSON
 * @param size Buffer size
 * @return 1 on success, 0 on failure
 */
int kaim_get_status(char* status_json, int size);

} // extern "C"

#endif // KAIM_LIB_H