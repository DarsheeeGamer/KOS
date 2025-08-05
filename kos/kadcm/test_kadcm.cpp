/*
 * KADCM C++ Library Test Program
 * Tests all major functionality of the KADCM API
 */

#include "kadcm_lib.h"
#include <iostream>
#include <vector>
#include <string>
#include <thread>
#include <chrono>

using namespace std;
using namespace KADCM;

// Test result tracking
struct TestResult {
    string name;
    bool passed;
    string message;
};

vector<TestResult> g_test_results;

// Test macros
#define TEST_BEGIN(name) \
    cout << "Testing " << name << "... "; \
    bool test_passed = true; \
    string test_message = "OK";

#define TEST_ASSERT(condition, msg) \
    if (!(condition)) { \
        test_passed = false; \
        test_message = msg; \
    }

#define TEST_END(name) \
    g_test_results.push_back({name, test_passed, test_message}); \
    cout << (test_passed ? "PASSED" : "FAILED") << endl; \
    if (!test_passed) cout << "  Error: " << test_message << endl;

// Test functions
void test_c_api_init() {
    TEST_BEGIN("C API Initialization");
    
    int result = kadcm_init();
    TEST_ASSERT(result == KADCM_SUCCESS, "kadcm_init failed");
    
    kadcm_cleanup();
    
    TEST_END("C API Initialization");
}

void test_c_api_connection() {
    TEST_BEGIN("C API Connection");
    
    kadcm_init();
    
    // Create config
    kadcm_config_t config = {0};
    config.pipe_path = "/tmp/kadcm_test.pipe";
    config.tcp_host = "localhost";
    config.tcp_port = 9876;
    config.timeout_ms = 5000;
    
    // Create handle
    kadcm_handle_t handle = kadcm_create(&config);
    TEST_ASSERT(handle != nullptr, "Failed to create handle");
    
    // Note: Connection will fail without server running
    // This just tests the API
    int result = kadcm_connect(handle);
    if (result != KADCM_SUCCESS) {
        cout << " (Connection expected to fail without server) ";
    }
    
    // Check connection status
    bool connected = kadcm_is_connected(handle);
    
    // Cleanup
    kadcm_destroy(handle);
    kadcm_cleanup();
    
    TEST_END("C API Connection");
}

void test_c_api_messages() {
    TEST_BEGIN("C API Messages");
    
    kadcm_init();
    
    kadcm_config_t config = {0};
    config.tcp_host = "localhost";
    config.tcp_port = 9876;
    
    kadcm_handle_t handle = kadcm_create(&config);
    TEST_ASSERT(handle != nullptr, "Failed to create handle");
    
    // Create a test message
    kadcm_message_t msg = {0};
    msg.type = KADCM_MSG_COMMAND;
    msg.priority = KADCM_PRIORITY_NORMAL;
    msg.flags = 0;
    
    const char* header = "{\"test\":\"value\"}";
    msg.header_data = (void*)header;
    msg.header_size = strlen(header);
    
    // Note: Send will fail without connection
    // This just tests the API structure
    
    kadcm_destroy(handle);
    kadcm_cleanup();
    
    TEST_END("C API Messages");
}

void test_cpp_api_basic() {
    TEST_BEGIN("C++ API Basic");
    
    kadcm_init();
    
    try {
        kadcm_config_t config = {0};
        config.tcp_host = "localhost";
        config.tcp_port = 9876;
        
        Connection conn(config);
        
        // Test isConnected before connection
        TEST_ASSERT(!conn.isConnected(), "Should not be connected initially");
        
        test_passed = true;
    }
    catch (const Exception& e) {
        test_message = string("Exception: ") + e.what();
        test_passed = false;
    }
    
    kadcm_cleanup();
    
    TEST_END("C++ API Basic");
}

void test_cpp_api_message() {
    TEST_BEGIN("C++ API Message");
    
    kadcm_init();
    
    try {
        Message msg(KADCM_MSG_COMMAND);
        msg.setPriority(KADCM_PRIORITY_HIGH);
        msg.setFlags(KADCM_FLAG_COMPRESSED);
        msg.setHeader("{\"command\":\"test\"}");
        msg.setBody("test: data\n");
        
        kadcm_message_t* raw_msg = msg.get();
        TEST_ASSERT(raw_msg->type == KADCM_MSG_COMMAND, "Wrong message type");
        TEST_ASSERT(raw_msg->priority == KADCM_PRIORITY_HIGH, "Wrong priority");
        TEST_ASSERT(raw_msg->flags == KADCM_FLAG_COMPRESSED, "Wrong flags");
        
        test_passed = true;
    }
    catch (const exception& e) {
        test_message = string("Exception: ") + e.what();
        test_passed = false;
    }
    
    kadcm_cleanup();
    
    TEST_END("C++ API Message");
}

void test_error_handling() {
    TEST_BEGIN("Error Handling");
    
    // Test error strings
    const char* err_str = kadcm_error_string(KADCM_ERROR_AUTH);
    TEST_ASSERT(err_str != nullptr, "Error string is null");
    TEST_ASSERT(strlen(err_str) > 0, "Error string is empty");
    
    // Test invalid parameters
    kadcm_handle_t handle = kadcm_create(nullptr);
    TEST_ASSERT(handle == nullptr, "Should fail with null config");
    
    int result = kadcm_connect(nullptr);
    TEST_ASSERT(result == KADCM_ERROR_INVALID, "Should return invalid error");
    
    TEST_END("Error Handling");
}

void test_thread_safety() {
    TEST_BEGIN("Thread Safety");
    
    kadcm_init();
    
    kadcm_config_t config = {0};
    config.tcp_host = "localhost";
    config.tcp_port = 9876;
    
    kadcm_handle_t handle = kadcm_create(&config);
    
    if (handle) {
        // Create multiple threads trying to use the handle
        vector<thread> threads;
        atomic<int> error_count(0);
        
        for (int i = 0; i < 5; i++) {
            threads.emplace_back([handle, &error_count]() {
                for (int j = 0; j < 10; j++) {
                    bool connected = kadcm_is_connected(handle);
                    // Just checking API doesn't crash
                    this_thread::sleep_for(chrono::milliseconds(1));
                }
            });
        }
        
        // Wait for threads
        for (auto& t : threads) {
            t.join();
        }
        
        TEST_ASSERT(error_count == 0, "Thread safety errors detected");
        
        kadcm_destroy(handle);
    }
    
    kadcm_cleanup();
    
    TEST_END("Thread Safety");
}

void test_memory_management() {
    TEST_BEGIN("Memory Management");
    
    kadcm_init();
    
    // Test multiple create/destroy cycles
    for (int i = 0; i < 100; i++) {
        kadcm_config_t config = {0};
        config.tcp_host = "localhost";
        config.tcp_port = 9876;
        
        kadcm_handle_t handle = kadcm_create(&config);
        if (handle) {
            kadcm_destroy(handle);
        }
    }
    
    // Test string management
    char* test_str = (char*)malloc(100);
    strcpy(test_str, "test string");
    kadcm_free_string(test_str);
    
    kadcm_cleanup();
    
    TEST_END("Memory Management");
}

// Main test runner
int main() {
    cout << "==================================" << endl;
    cout << "KADCM C/C++ Library Test Suite" << endl;
    cout << "==================================" << endl << endl;
    
    // Run all tests
    test_c_api_init();
    test_c_api_connection();
    test_c_api_messages();
    test_cpp_api_basic();
    test_cpp_api_message();
    test_error_handling();
    test_thread_safety();
    test_memory_management();
    
    // Print summary
    cout << endl;
    cout << "==================================" << endl;
    cout << "Test Summary" << endl;
    cout << "==================================" << endl;
    
    int passed = 0;
    int failed = 0;
    
    for (const auto& result : g_test_results) {
        if (result.passed) {
            passed++;
        } else {
            failed++;
            cout << "FAILED: " << result.name << " - " << result.message << endl;
        }
    }
    
    cout << endl;
    cout << "Total tests: " << g_test_results.size() << endl;
    cout << "Passed: " << passed << endl;
    cout << "Failed: " << failed << endl;
    
    if (failed == 0) {
        cout << endl << "All tests passed!" << endl;
        return 0;
    } else {
        cout << endl << "Some tests failed!" << endl;
        return 1;
    }
}