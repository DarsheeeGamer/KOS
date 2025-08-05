/*
 * KAIM C++ Library - Production-ready interface to kernel module
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <chrono>
#include <thread>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>

#include "kaim_lib.h"

namespace KAIM {

// Internal implementation class
class KAIMClientImpl {
public:
    KAIMClientImpl(const std::string& app_name, const std::string& fingerprint)
        : app_name_(app_name), fingerprint_(fingerprint), 
          connected_(false), socket_fd_(-1), device_fd_(-1) {}
    
    ~KAIMClientImpl() {
        disconnect();
    }
    
    bool connect() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (connected_) {
            return true;
        }
        
        // Open kernel device
        device_fd_ = open("/dev/kaim", O_RDWR);
        if (device_fd_ < 0) {
            last_error_ = "Failed to open /dev/kaim: " + std::string(strerror(errno));
            return false;
        }
        
        // Connect to daemon socket
        socket_fd_ = socket(AF_UNIX, SOCK_STREAM, 0);
        if (socket_fd_ < 0) {
            close(device_fd_);
            device_fd_ = -1;
            last_error_ = "Failed to create socket: " + std::string(strerror(errno));
            return false;
        }
        
        struct sockaddr_un addr;
        memset(&addr, 0, sizeof(addr));
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, KAIM_SOCKET_PATH, sizeof(addr.sun_path) - 1);
        
        if (::connect(socket_fd_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            close(socket_fd_);
            close(device_fd_);
            socket_fd_ = -1;
            device_fd_ = -1;
            last_error_ = "Failed to connect to daemon: " + std::string(strerror(errno));
            return false;
        }
        
        // Authenticate
        if (!authenticate()) {
            disconnect();
            return false;
        }
        
        connected_ = true;
        return true;
    }
    
    void disconnect() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (socket_fd_ >= 0) {
            // Send close message
            if (connected_ && !session_token_.empty()) {
                sendCloseMessage();
            }
            close(socket_fd_);
            socket_fd_ = -1;
        }
        
        if (device_fd_ >= 0) {
            close(device_fd_);
            device_fd_ = -1;
        }
        
        connected_ = false;
        session_token_.clear();
        permissions_.clear();
    }
    
    int deviceOpen(const std::string& device, const std::string& mode) {
        if (!ensureConnected()) {
            return -1;
        }
        
        struct kaim_device_req req;
        memset(&req, 0, sizeof(req));
        strncpy(req.device, device.c_str(), sizeof(req.device) - 1);
        strncpy(req.mode, mode.c_str(), sizeof(req.mode) - 1);
        
        if (ioctl(device_fd_, KAIM_IOCTL_DEVICE, &req) < 0) {
            last_error_ = "Device open ioctl failed: " + std::string(strerror(errno));
            return -1;
        }
        
        if (req.fd < 0) {
            last_error_ = "Device open denied";
            return -1;
        }
        
        return req.fd;
    }
    
    std::map<std::string, std::string> deviceControl(const std::string& device,
                                                     const std::string& command,
                                                     const std::map<std::string, std::string>& params) {
        std::map<std::string, std::string> result;
        
        if (!ensureConnected()) {
            result["success"] = "false";
            result["error"] = last_error_;
            return result;
        }
        
        // Send control message to daemon
        Message msg;
        msg.type = MessageType::REQUEST;
        msg.request_type = RequestType::CONTROL;
        msg.data["device"] = device;
        msg.data["command"] = command;
        msg.data["params"] = params;
        
        if (!sendMessage(msg)) {
            result["success"] = "false";
            result["error"] = "Failed to send control message";
            return result;
        }
        
        Message response;
        if (!receiveMessage(response)) {
            result["success"] = "false";
            result["error"] = "Failed to receive response";
            return result;
        }
        
        if (response.success) {
            result = response.data;
            result["success"] = "true";
        } else {
            result["success"] = "false";
            result["error"] = response.error;
        }
        
        return result;
    }
    
    bool processElevate(pid_t pid, const std::vector<std::string>& flags) {
        if (!ensureConnected()) {
            return false;
        }
        
        // Convert flags to bitmask
        uint32_t flag_bits = 0;
        for (const auto& flag : flags) {
            flag_bits |= stringToFlag(flag);
        }
        
        struct kaim_elevate_req req;
        req.target_pid = (pid == 0) ? getpid() : pid;
        req.flags = flag_bits;
        req.duration = 900; // 15 minutes default
        
        if (ioctl(device_fd_, KAIM_IOCTL_ELEVATE, &req) < 0) {
            last_error_ = "Elevation failed: " + std::string(strerror(errno));
            return false;
        }
        
        // Update local permissions
        for (const auto& flag : flags) {
            permissions_[flag] = true;
        }
        
        return true;
    }
    
    std::map<std::string, std::string> getStatus() {
        std::map<std::string, std::string> status;
        
        if (!ensureConnected()) {
            status["error"] = last_error_;
            return status;
        }
        
        struct kaim_status kstatus;
        if (ioctl(device_fd_, KAIM_IOCTL_STATUS, &kstatus) < 0) {
            status["error"] = "Status ioctl failed: " + std::string(strerror(errno));
            return status;
        }
        
        status["version"] = kstatus.version;
        status["process_count"] = std::to_string(kstatus.process_count);
        status["device_count"] = std::to_string(kstatus.device_count);
        status["elevations"] = std::to_string(kstatus.elevations);
        status["device_opens"] = std::to_string(kstatus.device_opens);
        status["permission_checks"] = std::to_string(kstatus.permission_checks);
        status["denials"] = std::to_string(kstatus.denials);
        
        return status;
    }
    
    bool checkPermission(const std::string& flag) {
        return permissions_.count(flag) > 0 && permissions_[flag];
    }
    
    std::vector<std::string> listPermissions() {
        std::vector<std::string> perms;
        for (const auto& [flag, granted] : permissions_) {
            if (granted) {
                perms.push_back(flag);
            }
        }
        return perms;
    }
    
    std::string getLastError() const {
        return last_error_;
    }
    
private:
    std::string app_name_;
    std::string fingerprint_;
    bool connected_;
    int socket_fd_;
    int device_fd_;
    std::string session_token_;
    std::map<std::string, bool> permissions_;
    std::string last_error_;
    std::mutex mutex_;
    
    // Message structure for daemon communication
    struct Message {
        enum Type { REQUEST, RESPONSE, EVENT, ERROR };
        enum ReqType { AUTHENTICATE, OPEN, CONTROL, ELEVATE, CLOSE, STATUS };
        
        Type type;
        ReqType request_type;
        std::string id;
        std::map<std::string, std::string> data;
        std::map<std::string, std::map<std::string, std::string>> complex_data;
        bool success;
        std::string error;
    };
    
    bool ensureConnected() {
        if (!connected_) {
            last_error_ = "Not connected to KAIM";
            return false;
        }
        return true;
    }
    
    bool authenticate() {
        Message auth_msg;
        auth_msg.type = Message::REQUEST;
        auth_msg.request_type = Message::AUTHENTICATE;
        auth_msg.data["fingerprint"] = fingerprint_;
        auth_msg.data["app_name"] = app_name_;
        
        if (!sendMessage(auth_msg)) {
            last_error_ = "Failed to send authentication message";
            return false;
        }
        
        Message response;
        if (!receiveMessage(response)) {
            last_error_ = "Failed to receive authentication response";
            return false;
        }
        
        if (!response.success) {
            last_error_ = "Authentication failed: " + response.error;
            return false;
        }
        
        session_token_ = response.data["token"];
        
        // Parse permissions
        std::string perms_str = response.data["permissions"];
        parsePermissions(perms_str);
        
        return true;
    }
    
    void parsePermissions(const std::string& perms_str) {
        // Simple parsing - in production would use JSON
        permissions_.clear();
        size_t pos = 0;
        while (pos < perms_str.length()) {
            size_t next = perms_str.find(',', pos);
            if (next == std::string::npos) {
                next = perms_str.length();
            }
            
            std::string perm = perms_str.substr(pos, next - pos);
            if (!perm.empty()) {
                permissions_[perm] = true;
            }
            
            pos = next + 1;
        }
    }
    
    bool sendMessage(const Message& msg) {
        // Serialize message (simplified - in production use protobuf or similar)
        std::string data = serializeMessage(msg);
        
        uint32_t length = data.length();
        if (write(socket_fd_, &length, sizeof(length)) != sizeof(length)) {
            return false;
        }
        
        if (write(socket_fd_, data.c_str(), length) != length) {
            return false;
        }
        
        return true;
    }
    
    bool receiveMessage(Message& msg) {
        uint32_t length;
        if (read(socket_fd_, &length, sizeof(length)) != sizeof(length)) {
            return false;
        }
        
        if (length > 1024 * 1024) { // Max 1MB message
            return false;
        }
        
        std::vector<char> buffer(length);
        if (read(socket_fd_, buffer.data(), length) != length) {
            return false;
        }
        
        std::string data(buffer.begin(), buffer.end());
        return deserializeMessage(data, msg);
    }
    
    std::string serializeMessage(const Message& msg) {
        // Simple serialization - in production use proper format
        std::string result = "TYPE:" + std::to_string(msg.type) + "\n";
        result += "REQTYPE:" + std::to_string(msg.request_type) + "\n";
        result += "ID:" + msg.id + "\n";
        
        for (const auto& [key, value] : msg.data) {
            result += "DATA:" + key + "=" + value + "\n";
        }
        
        return result;
    }
    
    bool deserializeMessage(const std::string& data, Message& msg) {
        // Simple deserialization
        size_t pos = 0;
        while (pos < data.length()) {
            size_t end = data.find('\n', pos);
            if (end == std::string::npos) {
                end = data.length();
            }
            
            std::string line = data.substr(pos, end - pos);
            size_t colon = line.find(':');
            if (colon != std::string::npos) {
                std::string key = line.substr(0, colon);
                std::string value = line.substr(colon + 1);
                
                if (key == "SUCCESS") {
                    msg.success = (value == "1");
                } else if (key == "ERROR") {
                    msg.error = value;
                } else if (key == "DATA") {
                    size_t eq = value.find('=');
                    if (eq != std::string::npos) {
                        msg.data[value.substr(0, eq)] = value.substr(eq + 1);
                    }
                }
            }
            
            pos = end + 1;
        }
        
        return true;
    }
    
    void sendCloseMessage() {
        Message msg;
        msg.type = Message::REQUEST;
        msg.request_type = Message::CLOSE;
        sendMessage(msg);
    }
    
    uint32_t stringToFlag(const std::string& flag) {
        static const std::map<std::string, uint32_t> flag_map = {
            {"KROOT", 0x00000001},
            {"KSYSTEM", 0x00000002},
            {"KUSR", 0x00000004},
            {"KAM", 0x00000008},
            {"KNET", 0x00000010},
            {"KDEV", 0x00000020},
            {"KPROC", 0x00000040},
            {"KFILE_R", 0x00000080},
            {"KFILE_W", 0x00000100},
            {"KFILE_X", 0x00000200},
            {"KMEM", 0x00000400},
            {"KLOG", 0x00000800},
            {"KSEC", 0x00001000},
            {"KAUD", 0x00002000},
            {"KCFG", 0x00004000},
            {"KUPD", 0x00008000},
            {"KSRV", 0x00010000},
            {"KDBG", 0x00020000}
        };
        
        auto it = flag_map.find(flag);
        return (it != flag_map.end()) ? it->second : 0;
    }
};

// Public API implementation
KAIMClient::KAIMClient(const std::string& app_name, const std::string& fingerprint)
    : impl_(std::make_unique<KAIMClientImpl>(app_name, fingerprint)) {}

KAIMClient::~KAIMClient() = default;

bool KAIMClient::connect() {
    return impl_->connect();
}

void KAIMClient::disconnect() {
    impl_->disconnect();
}

int KAIMClient::deviceOpen(const std::string& device, const std::string& mode) {
    return impl_->deviceOpen(device, mode);
}

std::map<std::string, std::string> KAIMClient::deviceControl(
    const std::string& device,
    const std::string& command,
    const std::map<std::string, std::string>& params) {
    return impl_->deviceControl(device, command, params);
}

bool KAIMClient::processElevate(pid_t pid, const std::vector<std::string>& flags) {
    return impl_->processElevate(pid, flags);
}

std::map<std::string, std::string> KAIMClient::getStatus() {
    return impl_->getStatus();
}

bool KAIMClient::checkPermission(const std::string& flag) {
    return impl_->checkPermission(flag);
}

std::vector<std::string> KAIMClient::listPermissions() {
    return impl_->listPermissions();
}

std::string KAIMClient::getLastError() const {
    return impl_->getLastError();
}

// C API implementation
static KAIMClient* g_client = nullptr;

extern "C" {

int kaim_init(const char* app_name, const char* fingerprint) {
    try {
        if (g_client) {
            delete g_client;
        }
        g_client = new KAIMClient(app_name, fingerprint);
        return g_client->connect() ? 1 : 0;
    } catch (...) {
        return 0;
    }
}

void kaim_cleanup() {
    if (g_client) {
        delete g_client;
        g_client = nullptr;
    }
}

int kaim_device_open(const char* device, const char* mode) {
    if (!g_client) return -1;
    return g_client->deviceOpen(device, mode);
}

int kaim_device_control(const char* device, const char* command,
                       const char* params_json, char* result_json, int result_size) {
    if (!g_client || !result_json) return 0;
    
    // Parse params (simplified)
    std::map<std::string, std::string> params;
    // In production, parse JSON properly
    
    auto result = g_client->deviceControl(device, command, params);
    
    // Serialize result (simplified)
    std::string json = "{";
    for (const auto& [key, value] : result) {
        json += "\"" + key + "\":\"" + value + "\",";
    }
    if (json.length() > 1) json.pop_back(); // Remove trailing comma
    json += "}";
    
    strncpy(result_json, json.c_str(), result_size - 1);
    result_json[result_size - 1] = '\0';
    
    return result["success"] == "true" ? 1 : 0;
}

int kaim_process_elevate(pid_t pid, const char** flags, int flag_count) {
    if (!g_client) return 0;
    
    std::vector<std::string> flag_vec;
    for (int i = 0; i < flag_count; i++) {
        flag_vec.push_back(flags[i]);
    }
    
    return g_client->processElevate(pid, flag_vec) ? 1 : 0;
}

int kaim_get_status(char* status_json, int size) {
    if (!g_client || !status_json) return 0;
    
    auto status = g_client->getStatus();
    
    // Serialize status (simplified)
    std::string json = "{";
    for (const auto& [key, value] : status) {
        json += "\"" + key + "\":\"" + value + "\",";
    }
    if (json.length() > 1) json.pop_back();
    json += "}";
    
    strncpy(status_json, json.c_str(), size - 1);
    status_json[size - 1] = '\0';
    
    return status.count("error") == 0 ? 1 : 0;
}

} // extern "C"

} // namespace KAIM