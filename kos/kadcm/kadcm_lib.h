/*
 * KADCM C/C++ Library Header
 * Kaede Advanced Device Communication Manager API
 * 
 * This library provides C and C++ applications with secure communication
 * between host OS and KOS through encrypted tunnels.
 */

#ifndef __KADCM_LIB_H__
#define __KADCM_LIB_H__

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* Version information */
#define KADCM_VERSION_MAJOR 1
#define KADCM_VERSION_MINOR 0
#define KADCM_VERSION_PATCH 0

/* Error codes */
#define KADCM_SUCCESS           0
#define KADCM_ERROR_GENERAL    -1
#define KADCM_ERROR_AUTH       -2
#define KADCM_ERROR_CONNECT    -3
#define KADCM_ERROR_TIMEOUT    -4
#define KADCM_ERROR_PROTOCOL   -5
#define KADCM_ERROR_PERMISSION -6
#define KADCM_ERROR_INVALID    -7
#define KADCM_ERROR_NOMEM      -8
#define KADCM_ERROR_BUSY       -9
#define KADCM_ERROR_TLS        -10

/* Message types */
typedef enum {
    KADCM_MSG_COMMAND  = 1,
    KADCM_MSG_DATA     = 2,
    KADCM_MSG_AUTH     = 3,
    KADCM_MSG_CONTROL  = 4,
    KADCM_MSG_HEARTBEAT = 5,
    KADCM_MSG_ERROR    = 6,
    KADCM_MSG_NOTIFY   = 7
} kadcm_msg_type_t;

/* Message priority */
typedef enum {
    KADCM_PRIORITY_LOW    = 0,
    KADCM_PRIORITY_NORMAL = 1,
    KADCM_PRIORITY_HIGH   = 2,
    KADCM_PRIORITY_URGENT = 3
} kadcm_priority_t;

/* Message flags */
#define KADCM_FLAG_COMPRESSED  0x01
#define KADCM_FLAG_ENCRYPTED   0x02
#define KADCM_FLAG_RESPONSE    0x04

/* Connection handle */
typedef struct kadcm_connection* kadcm_handle_t;

/* Message structure */
typedef struct {
    uint32_t id;
    kadcm_msg_type_t type;
    kadcm_priority_t priority;
    uint8_t flags;
    void* header_data;    /* JSON header */
    size_t header_size;
    void* body_data;      /* YAML body */
    size_t body_size;
} kadcm_message_t;

/* Callback function types */
typedef void (*kadcm_notify_callback_t)(kadcm_handle_t handle, const kadcm_message_t* msg, void* user_data);
typedef void (*kadcm_error_callback_t)(kadcm_handle_t handle, int error_code, const char* error_msg, void* user_data);

/* Configuration structure */
typedef struct {
    const char* pipe_path;      /* Named pipe path (platform-specific) */
    const char* tcp_host;       /* TCP fallback host */
    uint16_t tcp_port;          /* TCP fallback port */
    const char* tls_cert;       /* TLS certificate path */
    const char* tls_key;        /* TLS key path */
    bool verify_peer;           /* Verify peer certificate */
    uint32_t timeout_ms;        /* Connection timeout in milliseconds */
    uint32_t heartbeat_interval;/* Heartbeat interval in seconds */
} kadcm_config_t;

/* Initialize library (call once) */
int kadcm_init(void);

/* Cleanup library (call on exit) */
void kadcm_cleanup(void);

/* Create connection handle */
kadcm_handle_t kadcm_create(const kadcm_config_t* config);

/* Destroy connection handle */
void kadcm_destroy(kadcm_handle_t handle);

/* Connect to KADCM server */
int kadcm_connect(kadcm_handle_t handle);

/* Disconnect from server */
void kadcm_disconnect(kadcm_handle_t handle);

/* Check if connected */
bool kadcm_is_connected(kadcm_handle_t handle);

/* Authenticate with fingerprint */
int kadcm_authenticate(kadcm_handle_t handle, const char* entity_type, 
                      const char* entity_id, const char* fingerprint);

/* Send message */
int kadcm_send_message(kadcm_handle_t handle, const kadcm_message_t* msg);

/* Receive message (blocking) */
int kadcm_recv_message(kadcm_handle_t handle, kadcm_message_t* msg, uint32_t timeout_ms);

/* Execute command */
int kadcm_exec_command(kadcm_handle_t handle, const char* command, 
                      const char* args[], char** output, size_t* output_size);

/* File operations */
int kadcm_file_read(kadcm_handle_t handle, const char* path, 
                   void** data, size_t* size);
int kadcm_file_write(kadcm_handle_t handle, const char* path, 
                    const void* data, size_t size);
int kadcm_file_delete(kadcm_handle_t handle, const char* path);
int kadcm_file_copy(kadcm_handle_t handle, const char* src, const char* dst);
int kadcm_file_move(kadcm_handle_t handle, const char* src, const char* dst);

/* Directory operations */
int kadcm_dir_list(kadcm_handle_t handle, const char* path, 
                  char*** entries, size_t* count);
int kadcm_dir_create(kadcm_handle_t handle, const char* path);
int kadcm_dir_delete(kadcm_handle_t handle, const char* path);

/* Process management */
int kadcm_process_list(kadcm_handle_t handle, uint32_t** pids, size_t* count);
int kadcm_process_info(kadcm_handle_t handle, uint32_t pid, char** info);
int kadcm_process_kill(kadcm_handle_t handle, uint32_t pid, int signal);

/* Callbacks */
void kadcm_set_notify_callback(kadcm_handle_t handle, kadcm_notify_callback_t cb, void* user_data);
void kadcm_set_error_callback(kadcm_handle_t handle, kadcm_error_callback_t cb, void* user_data);

/* Utility functions */
const char* kadcm_error_string(int error_code);
void kadcm_free_string(char* str);
void kadcm_free_array(void* array);
void kadcm_message_free(kadcm_message_t* msg);

#ifdef __cplusplus
}

/* C++ API */
namespace KADCM {

class Connection {
public:
    // Constructors/destructors
    Connection(const kadcm_config_t& config);
    ~Connection();
    
    // Connection management
    bool connect();
    void disconnect();
    bool isConnected() const;
    
    // Authentication
    bool authenticate(const std::string& entityType, 
                     const std::string& entityId,
                     const std::string& fingerprint);
    
    // Command execution
    std::string executeCommand(const std::string& command,
                              const std::vector<std::string>& args);
    
    // File operations
    std::vector<uint8_t> readFile(const std::string& path);
    void writeFile(const std::string& path, const std::vector<uint8_t>& data);
    void deleteFile(const std::string& path);
    void copyFile(const std::string& src, const std::string& dst);
    void moveFile(const std::string& src, const std::string& dst);
    
    // Directory operations
    std::vector<std::string> listDirectory(const std::string& path);
    void createDirectory(const std::string& path);
    void deleteDirectory(const std::string& path);
    
    // Process management
    std::vector<uint32_t> listProcesses();
    std::string getProcessInfo(uint32_t pid);
    void killProcess(uint32_t pid, int signal = 15);
    
    // Message handling
    void sendMessage(const kadcm_message_t& msg);
    bool receiveMessage(kadcm_message_t& msg, uint32_t timeoutMs = 0);
    
    // Callbacks
    void setNotifyCallback(std::function<void(const kadcm_message_t&)> callback);
    void setErrorCallback(std::function<void(int, const std::string&)> callback);
    
private:
    kadcm_handle_t handle_;
    std::function<void(const kadcm_message_t&)> notifyCallback_;
    std::function<void(int, const std::string&)> errorCallback_;
    
    // Disable copy
    Connection(const Connection&) = delete;
    Connection& operator=(const Connection&) = delete;
};

// Utility classes
class Message {
public:
    Message(kadcm_msg_type_t type = KADCM_MSG_COMMAND);
    ~Message();
    
    void setType(kadcm_msg_type_t type);
    void setPriority(kadcm_priority_t priority);
    void setFlags(uint8_t flags);
    void setHeader(const std::string& json);
    void setBody(const std::string& yaml);
    
    kadcm_message_t* get() { return &msg_; }
    const kadcm_message_t* get() const { return &msg_; }
    
private:
    kadcm_message_t msg_;
    std::string header_;
    std::string body_;
};

// Exception class
class Exception : public std::exception {
public:
    Exception(int code, const std::string& msg) 
        : code_(code), msg_(msg) {}
    
    const char* what() const noexcept override { return msg_.c_str(); }
    int code() const { return code_; }
    
private:
    int code_;
    std::string msg_;
};

} // namespace KADCM

#endif /* __cplusplus */

#endif /* __KADCM_LIB_H__ */