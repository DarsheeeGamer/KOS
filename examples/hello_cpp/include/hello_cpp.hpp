/*
 * hello_cpp.hpp - Main header for hello_cpp
 */

#ifndef HELLO_CPP_HPP
#define HELLO_CPP_HPP

#include <string>
#include <exception>

namespace hello_cpp {

// Constants
constexpr const char* APP_NAME = "hello_cpp";
constexpr const char* APP_VERSION = "1.0.0";

// Custom exception class
class hello_cppException : public std::exception {
private:
    std::string message;
    
public:
    explicit hello_cppException(const std::string& msg) : message(msg) {}
    
    const char* what() const noexcept override {
        return message.c_str();
    }
};

// Application configuration
struct Config {
    std::string name = APP_NAME;
    std::string version = APP_VERSION;
    bool debugMode = false;
};

// Add your class declarations here

} // namespace hello_cpp

#endif // HELLO_CPP_HPP
