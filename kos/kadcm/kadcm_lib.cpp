/*
 * KADCM C++ Library Implementation
 * Kaede Advanced Device Communication Manager
 */

#include "kadcm_lib.h"
#include <cstring>
#include <cstdlib>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <atomic>
#include <sstream>
#include <chrono>

#ifdef _WIN32
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <sys/socket.h>
#include <sys/un.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#endif

#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/rand.h>

/* Internal structures */
struct kadcm_connection {
    kadcm_config_t config;
    SSL_CTX* ssl_ctx;
    SSL* ssl;
    int socket_fd;
#ifdef _WIN32
    HANDLE pipe_handle;
#endif
    std::atomic<bool> connected;
    std::atomic<bool> authenticated;
    std::string session_id;
    
    /* Callbacks */
    kadcm_notify_callback_t notify_cb;
    kadcm_error_callback_t error_cb;
    void* cb_user_data;
    
    /* Threading */
    std::thread receiver_thread;
    std::mutex send_mutex;
    std::mutex recv_mutex;
    std::atomic<bool> running;
    
    /* Message tracking */
    std::atomic<uint32_t> next_msg_id;
    std::map<uint32_t, kadcm_message_t*> pending_responses;
    std::mutex response_mutex;
};

/* Global state */
static std::mutex g_init_mutex;
static bool g_initialized = false;
static SSL_CTX* g_default_ssl_ctx = nullptr;

/* Error messages */
static const char* g_error_strings[] = {
    "Success",
    "General error",
    "Authentication failed",
    "Connection failed",
    "Operation timed out",
    "Protocol error",
    "Permission denied",
    "Invalid parameter",
    "Out of memory",
    "Resource busy",
    "TLS/SSL error"
};

/* Forward declarations */
static void receiver_thread_func(kadcm_connection* conn);
static int send_raw_message(kadcm_connection* conn, const void* data, size_t size);
static int recv_raw_message(kadcm_connection* conn, void** data, size_t* size, uint32_t timeout_ms);
static kadcm_message_t* create_message(kadcm_msg_type_t type);
static void free_message_internal(kadcm_message_t* msg);

/* Initialize library */
int kadcm_init(void) {
    std::lock_guard<std::mutex> lock(g_init_mutex);
    
    if (g_initialized) {
        return KADCM_SUCCESS;
    }
    
#ifdef _WIN32
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        return KADCM_ERROR_GENERAL;
    }
#endif
    
    /* Initialize OpenSSL */
    SSL_library_init();
    SSL_load_error_strings();
    OpenSSL_add_all_algorithms();
    
    /* Create default SSL context */
    g_default_ssl_ctx = SSL_CTX_new(TLS_client_method());
    if (!g_default_ssl_ctx) {
        return KADCM_ERROR_TLS;
    }
    
    /* Set default options */
    SSL_CTX_set_options(g_default_ssl_ctx, SSL_OP_NO_SSLv2 | SSL_OP_NO_SSLv3);
    SSL_CTX_set_min_proto_version(g_default_ssl_ctx, TLS1_2_VERSION);
    
    g_initialized = true;
    return KADCM_SUCCESS;
}

/* Cleanup library */
void kadcm_cleanup(void) {
    std::lock_guard<std::mutex> lock(g_init_mutex);
    
    if (!g_initialized) {
        return;
    }
    
    if (g_default_ssl_ctx) {
        SSL_CTX_free(g_default_ssl_ctx);
        g_default_ssl_ctx = nullptr;
    }
    
    EVP_cleanup();
    
#ifdef _WIN32
    WSACleanup();
#endif
    
    g_initialized = false;
}

/* Create connection handle */
kadcm_handle_t kadcm_create(const kadcm_config_t* config) {
    if (!config) {
        return nullptr;
    }
    
    kadcm_connection* conn = new (std::nothrow) kadcm_connection();
    if (!conn) {
        return nullptr;
    }
    
    /* Initialize connection */
    memset(conn, 0, sizeof(*conn));
    conn->config = *config;
    conn->socket_fd = -1;
#ifdef _WIN32
    conn->pipe_handle = INVALID_HANDLE_VALUE;
#endif
    conn->connected = false;
    conn->authenticated = false;
    conn->running = false;
    conn->next_msg_id = 1;
    
    /* Create SSL context */
    conn->ssl_ctx = SSL_CTX_new(TLS_client_method());
    if (!conn->ssl_ctx) {
        delete conn;
        return nullptr;
    }
    
    /* Configure SSL */
    SSL_CTX_set_options(conn->ssl_ctx, SSL_OP_NO_SSLv2 | SSL_OP_NO_SSLv3);
    SSL_CTX_set_min_proto_version(conn->ssl_ctx, TLS1_2_VERSION);
    
    /* Load certificates if provided */
    if (config->tls_cert && config->tls_key) {
        if (SSL_CTX_use_certificate_file(conn->ssl_ctx, config->tls_cert, SSL_FILETYPE_PEM) <= 0 ||
            SSL_CTX_use_PrivateKey_file(conn->ssl_ctx, config->tls_key, SSL_FILETYPE_PEM) <= 0) {
            SSL_CTX_free(conn->ssl_ctx);
            delete conn;
            return nullptr;
        }
    }
    
    if (config->verify_peer) {
        SSL_CTX_set_verify(conn->ssl_ctx, SSL_VERIFY_PEER, nullptr);
    }
    
    return conn;
}

/* Destroy connection handle */
void kadcm_destroy(kadcm_handle_t handle) {
    if (!handle) {
        return;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    /* Disconnect if connected */
    if (conn->connected) {
        kadcm_disconnect(handle);
    }
    
    /* Cleanup SSL */
    if (conn->ssl_ctx) {
        SSL_CTX_free(conn->ssl_ctx);
    }
    
    /* Free pending responses */
    {
        std::lock_guard<std::mutex> lock(conn->response_mutex);
        for (auto& pair : conn->pending_responses) {
            free_message_internal(pair.second);
        }
        conn->pending_responses.clear();
    }
    
    delete conn;
}

/* Connect to server */
int kadcm_connect(kadcm_handle_t handle) {
    if (!handle) {
        return KADCM_ERROR_INVALID;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (conn->connected) {
        return KADCM_ERROR_BUSY;
    }
    
#ifdef _WIN32
    /* Try named pipe first on Windows */
    if (conn->config.pipe_path) {
        conn->pipe_handle = CreateFileA(
            conn->config.pipe_path,
            GENERIC_READ | GENERIC_WRITE,
            0,
            nullptr,
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED,
            nullptr
        );
        
        if (conn->pipe_handle != INVALID_HANDLE_VALUE) {
            /* Set pipe mode */
            DWORD mode = PIPE_READMODE_MESSAGE;
            SetNamedPipeHandleState(conn->pipe_handle, &mode, nullptr, nullptr);
            
            conn->connected = true;
            goto connected;
        }
    }
#else
    /* Try Unix socket on Linux */
    if (conn->config.pipe_path) {
        conn->socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (conn->socket_fd >= 0) {
            struct sockaddr_un addr;
            memset(&addr, 0, sizeof(addr));
            addr.sun_family = AF_UNIX;
            strncpy(addr.sun_path, conn->config.pipe_path, sizeof(addr.sun_path) - 1);
            
            if (connect(conn->socket_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                conn->connected = true;
                goto connected;
            }
            
            close(conn->socket_fd);
            conn->socket_fd = -1;
        }
    }
#endif
    
    /* Fallback to TCP */
    if (conn->config.tcp_host && conn->config.tcp_port) {
        conn->socket_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (conn->socket_fd < 0) {
            return KADCM_ERROR_CONNECT;
        }
        
        struct sockaddr_in addr;
        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port = htons(conn->config.tcp_port);
        addr.sin_addr.s_addr = inet_addr(conn->config.tcp_host);
        
        if (connect(conn->socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
#ifdef _WIN32
            closesocket(conn->socket_fd);
#else
            close(conn->socket_fd);
#endif
            conn->socket_fd = -1;
            return KADCM_ERROR_CONNECT;
        }
        
        /* Setup SSL */
        conn->ssl = SSL_new(conn->ssl_ctx);
        if (!conn->ssl) {
#ifdef _WIN32
            closesocket(conn->socket_fd);
#else
            close(conn->socket_fd);
#endif
            conn->socket_fd = -1;
            return KADCM_ERROR_TLS;
        }
        
        SSL_set_fd(conn->ssl, conn->socket_fd);
        
        if (SSL_connect(conn->ssl) <= 0) {
            SSL_free(conn->ssl);
            conn->ssl = nullptr;
#ifdef _WIN32
            closesocket(conn->socket_fd);
#else
            close(conn->socket_fd);
#endif
            conn->socket_fd = -1;
            return KADCM_ERROR_TLS;
        }
        
        conn->connected = true;
    }
    
connected:
    if (conn->connected) {
        /* Start receiver thread */
        conn->running = true;
        conn->receiver_thread = std::thread(receiver_thread_func, conn);
        return KADCM_SUCCESS;
    }
    
    return KADCM_ERROR_CONNECT;
}

/* Disconnect from server */
void kadcm_disconnect(kadcm_handle_t handle) {
    if (!handle) {
        return;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (!conn->connected) {
        return;
    }
    
    /* Stop receiver thread */
    conn->running = false;
    if (conn->receiver_thread.joinable()) {
        conn->receiver_thread.join();
    }
    
    /* Close connections */
    if (conn->ssl) {
        SSL_shutdown(conn->ssl);
        SSL_free(conn->ssl);
        conn->ssl = nullptr;
    }
    
#ifdef _WIN32
    if (conn->pipe_handle != INVALID_HANDLE_VALUE) {
        CloseHandle(conn->pipe_handle);
        conn->pipe_handle = INVALID_HANDLE_VALUE;
    }
#endif
    
    if (conn->socket_fd >= 0) {
#ifdef _WIN32
        closesocket(conn->socket_fd);
#else
        close(conn->socket_fd);
#endif
        conn->socket_fd = -1;
    }
    
    conn->connected = false;
    conn->authenticated = false;
    conn->session_id.clear();
}

/* Check connection status */
bool kadcm_is_connected(kadcm_handle_t handle) {
    if (!handle) {
        return false;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    return conn->connected.load();
}

/* Authenticate */
int kadcm_authenticate(kadcm_handle_t handle, const char* entity_type,
                      const char* entity_id, const char* fingerprint) {
    if (!handle || !entity_type || !entity_id || !fingerprint) {
        return KADCM_ERROR_INVALID;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (!conn->connected) {
        return KADCM_ERROR_CONNECT;
    }
    
    /* Create auth message */
    kadcm_message_t* msg = create_message(KADCM_MSG_AUTH);
    if (!msg) {
        return KADCM_ERROR_NOMEM;
    }
    
    /* Build JSON header */
    std::stringstream header;
    header << "{\"entity_type\":\"" << entity_type << "\","
           << "\"entity_id\":\"" << entity_id << "\","
           << "\"fingerprint\":\"" << fingerprint << "\"}";
    
    std::string header_str = header.str();
    msg->header_data = malloc(header_str.size());
    memcpy(msg->header_data, header_str.c_str(), header_str.size());
    msg->header_size = header_str.size();
    
    /* Send message */
    int result = kadcm_send_message(handle, msg);
    free_message_internal(msg);
    
    if (result != KADCM_SUCCESS) {
        return result;
    }
    
    /* Wait for response */
    kadcm_message_t response;
    result = kadcm_recv_message(handle, &response, 5000);
    
    if (result == KADCM_SUCCESS) {
        conn->authenticated = true;
        /* Extract session ID from response */
        // TODO: Parse response and extract session_id
    }
    
    kadcm_message_free(&response);
    return result;
}

/* Send message */
int kadcm_send_message(kadcm_handle_t handle, const kadcm_message_t* msg) {
    if (!handle || !msg) {
        return KADCM_ERROR_INVALID;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (!conn->connected) {
        return KADCM_ERROR_CONNECT;
    }
    
    std::lock_guard<std::mutex> lock(conn->send_mutex);
    
    /* Assign message ID if not set */
    kadcm_message_t* mutable_msg = const_cast<kadcm_message_t*>(msg);
    if (mutable_msg->id == 0) {
        mutable_msg->id = conn->next_msg_id.fetch_add(1);
    }
    
    /* Serialize message */
    size_t total_size = 5 + msg->header_size + msg->body_size;
    uint8_t* buffer = (uint8_t*)malloc(total_size);
    if (!buffer) {
        return KADCM_ERROR_NOMEM;
    }
    
    /* Pack header: [4 bytes length][1 byte flags] */
    uint32_t data_length = msg->header_size + msg->body_size;
    buffer[0] = (data_length >> 24) & 0xFF;
    buffer[1] = (data_length >> 16) & 0xFF;
    buffer[2] = (data_length >> 8) & 0xFF;
    buffer[3] = data_length & 0xFF;
    buffer[4] = msg->flags;
    
    /* Copy data */
    if (msg->header_size > 0) {
        memcpy(buffer + 5, msg->header_data, msg->header_size);
    }
    if (msg->body_size > 0) {
        memcpy(buffer + 5 + msg->header_size, msg->body_data, msg->body_size);
    }
    
    /* Send */
    int result = send_raw_message(conn, buffer, total_size);
    free(buffer);
    
    return result;
}

/* Receive message */
int kadcm_recv_message(kadcm_handle_t handle, kadcm_message_t* msg, uint32_t timeout_ms) {
    if (!handle || !msg) {
        return KADCM_ERROR_INVALID;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (!conn->connected) {
        return KADCM_ERROR_CONNECT;
    }
    
    /* Check pending responses */
    {
        std::lock_guard<std::mutex> lock(conn->response_mutex);
        if (!conn->pending_responses.empty()) {
            auto it = conn->pending_responses.begin();
            *msg = *(it->second);
            free(it->second);
            conn->pending_responses.erase(it);
            return KADCM_SUCCESS;
        }
    }
    
    /* Wait for new message */
    auto start = std::chrono::steady_clock::now();
    
    while (true) {
        {
            std::lock_guard<std::mutex> lock(conn->response_mutex);
            if (!conn->pending_responses.empty()) {
                auto it = conn->pending_responses.begin();
                *msg = *(it->second);
                free(it->second);
                conn->pending_responses.erase(it);
                return KADCM_SUCCESS;
            }
        }
        
        if (timeout_ms > 0) {
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start).count();
            if (elapsed >= timeout_ms) {
                return KADCM_ERROR_TIMEOUT;
            }
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

/* Execute command */
int kadcm_exec_command(kadcm_handle_t handle, const char* command,
                      const char* args[], char** output, size_t* output_size) {
    if (!handle || !command || !output || !output_size) {
        return KADCM_ERROR_INVALID;
    }
    
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    
    if (!conn->connected || !conn->authenticated) {
        return KADCM_ERROR_CONNECT;
    }
    
    /* Build command message */
    kadcm_message_t* msg = create_message(KADCM_MSG_COMMAND);
    if (!msg) {
        return KADCM_ERROR_NOMEM;
    }
    
    /* Build JSON header */
    std::stringstream header;
    header << "{\"command\":\"" << command << "\",\"args\":[";
    
    if (args) {
        for (int i = 0; args[i] != nullptr; i++) {
            if (i > 0) header << ",";
            header << "\"" << args[i] << "\"";
        }
    }
    
    header << "]}";
    
    std::string header_str = header.str();
    msg->header_data = malloc(header_str.size());
    memcpy(msg->header_data, header_str.c_str(), header_str.size());
    msg->header_size = header_str.size();
    
    /* Send and wait for response */
    int result = kadcm_send_message(handle, msg);
    uint32_t msg_id = msg->id;
    free_message_internal(msg);
    
    if (result != KADCM_SUCCESS) {
        return result;
    }
    
    /* Wait for response with matching ID */
    kadcm_message_t response;
    result = kadcm_recv_message(handle, &response, 30000);  // 30 second timeout
    
    if (result == KADCM_SUCCESS) {
        /* Extract output from response body */
        *output = (char*)malloc(response.body_size + 1);
        if (*output) {
            memcpy(*output, response.body_data, response.body_size);
            (*output)[response.body_size] = '\0';
            *output_size = response.body_size;
        } else {
            result = KADCM_ERROR_NOMEM;
        }
        kadcm_message_free(&response);
    }
    
    return result;
}

/* Set callbacks */
void kadcm_set_notify_callback(kadcm_handle_t handle, kadcm_notify_callback_t cb, void* user_data) {
    if (!handle) return;
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    conn->notify_cb = cb;
    conn->cb_user_data = user_data;
}

void kadcm_set_error_callback(kadcm_handle_t handle, kadcm_error_callback_t cb, void* user_data) {
    if (!handle) return;
    kadcm_connection* conn = static_cast<kadcm_connection*>(handle);
    conn->error_cb = cb;
    conn->cb_user_data = user_data;
}

/* Utility functions */
const char* kadcm_error_string(int error_code) {
    int index = -error_code;
    if (index >= 0 && index < sizeof(g_error_strings) / sizeof(g_error_strings[0])) {
        return g_error_strings[index];
    }
    return "Unknown error";
}

void kadcm_free_string(char* str) {
    free(str);
}

void kadcm_free_array(void* array) {
    free(array);
}

void kadcm_message_free(kadcm_message_t* msg) {
    if (!msg) return;
    free_message_internal(msg);
}

/* Internal functions */
static kadcm_message_t* create_message(kadcm_msg_type_t type) {
    kadcm_message_t* msg = (kadcm_message_t*)calloc(1, sizeof(kadcm_message_t));
    if (msg) {
        msg->type = type;
        msg->priority = KADCM_PRIORITY_NORMAL;
    }
    return msg;
}

static void free_message_internal(kadcm_message_t* msg) {
    if (!msg) return;
    free(msg->header_data);
    free(msg->body_data);
    msg->header_data = nullptr;
    msg->body_data = nullptr;
    msg->header_size = 0;
    msg->body_size = 0;
}

static int send_raw_message(kadcm_connection* conn, const void* data, size_t size) {
#ifdef _WIN32
    if (conn->pipe_handle != INVALID_HANDLE_VALUE) {
        DWORD written;
        if (WriteFile(conn->pipe_handle, data, size, &written, nullptr)) {
            return KADCM_SUCCESS;
        }
        return KADCM_ERROR_GENERAL;
    }
#endif
    
    if (conn->ssl) {
        int written = SSL_write(conn->ssl, data, size);
        if (written == size) {
            return KADCM_SUCCESS;
        }
        return KADCM_ERROR_TLS;
    }
    
    if (conn->socket_fd >= 0) {
        ssize_t written = send(conn->socket_fd, data, size, 0);
        if (written == size) {
            return KADCM_SUCCESS;
        }
    }
    
    return KADCM_ERROR_GENERAL;
}

static void receiver_thread_func(kadcm_connection* conn) {
    uint8_t header[5];
    
    while (conn->running && conn->connected) {
        /* Read header */
        size_t bytes_read = 0;
        
#ifdef _WIN32
        if (conn->pipe_handle != INVALID_HANDLE_VALUE) {
            DWORD read;
            if (!ReadFile(conn->pipe_handle, header, 5, &read, nullptr) || read != 5) {
                break;
            }
            bytes_read = 5;
        }
#endif
        
        if (conn->ssl && bytes_read == 0) {
            int read = SSL_read(conn->ssl, header, 5);
            if (read != 5) {
                break;
            }
            bytes_read = 5;
        }
        
        if (conn->socket_fd >= 0 && bytes_read == 0) {
            ssize_t read = recv(conn->socket_fd, header, 5, MSG_WAITALL);
            if (read != 5) {
                break;
            }
            bytes_read = 5;
        }
        
        if (bytes_read != 5) {
            break;
        }
        
        /* Parse header */
        uint32_t data_length = (header[0] << 24) | (header[1] << 16) | 
                              (header[2] << 8) | header[3];
        uint8_t flags = header[4];
        
        /* Read data */
        uint8_t* data = (uint8_t*)malloc(data_length);
        if (!data) {
            break;
        }
        
        bytes_read = 0;
        
#ifdef _WIN32
        if (conn->pipe_handle != INVALID_HANDLE_VALUE) {
            DWORD read;
            if (!ReadFile(conn->pipe_handle, data, data_length, &read, nullptr) || 
                read != data_length) {
                free(data);
                break;
            }
            bytes_read = data_length;
        }
#endif
        
        if (conn->ssl && bytes_read == 0) {
            int read = SSL_read(conn->ssl, data, data_length);
            if (read != data_length) {
                free(data);
                break;
            }
            bytes_read = data_length;
        }
        
        if (conn->socket_fd >= 0 && bytes_read == 0) {
            ssize_t read = recv(conn->socket_fd, data, data_length, MSG_WAITALL);
            if (read != data_length) {
                free(data);
                break;
            }
            bytes_read = data_length;
        }
        
        /* Parse message (simplified - should parse JSON/YAML) */
        kadcm_message_t* msg = create_message(KADCM_MSG_DATA);
        msg->flags = flags;
        msg->header_data = data;
        msg->header_size = data_length;
        
        /* Handle message */
        if (msg->type == KADCM_MSG_NOTIFY && conn->notify_cb) {
            conn->notify_cb(conn, msg, conn->cb_user_data);
            free_message_internal(msg);
            free(msg);
        } else {
            /* Queue for recv_message */
            std::lock_guard<std::mutex> lock(conn->response_mutex);
            conn->pending_responses[msg->id] = msg;
        }
    }
    
    /* Connection lost */
    if (conn->error_cb) {
        conn->error_cb(conn, KADCM_ERROR_CONNECT, "Connection lost", conn->cb_user_data);
    }
}

/* C++ API Implementation */
namespace KADCM {

Connection::Connection(const kadcm_config_t& config) : handle_(nullptr) {
    handle_ = kadcm_create(&config);
    if (!handle_) {
        throw Exception(KADCM_ERROR_NOMEM, "Failed to create connection");
    }
}

Connection::~Connection() {
    if (handle_) {
        kadcm_destroy(handle_);
    }
}

bool Connection::connect() {
    int result = kadcm_connect(handle_);
    if (result != KADCM_SUCCESS) {
        throw Exception(result, kadcm_error_string(result));
    }
    return true;
}

void Connection::disconnect() {
    kadcm_disconnect(handle_);
}

bool Connection::isConnected() const {
    return kadcm_is_connected(handle_);
}

bool Connection::authenticate(const std::string& entityType,
                            const std::string& entityId,
                            const std::string& fingerprint) {
    int result = kadcm_authenticate(handle_, entityType.c_str(),
                                   entityId.c_str(), fingerprint.c_str());
    if (result != KADCM_SUCCESS) {
        throw Exception(result, kadcm_error_string(result));
    }
    return true;
}

std::string Connection::executeCommand(const std::string& command,
                                     const std::vector<std::string>& args) {
    // Convert args to C-style array
    std::vector<const char*> c_args;
    for (const auto& arg : args) {
        c_args.push_back(arg.c_str());
    }
    c_args.push_back(nullptr);
    
    char* output = nullptr;
    size_t output_size = 0;
    
    int result = kadcm_exec_command(handle_, command.c_str(),
                                   c_args.data(), &output, &output_size);
    
    if (result != KADCM_SUCCESS) {
        throw Exception(result, kadcm_error_string(result));
    }
    
    std::string ret(output, output_size);
    kadcm_free_string(output);
    return ret;
}

/* Additional C++ methods would be implemented similarly... */

} // namespace KADCM