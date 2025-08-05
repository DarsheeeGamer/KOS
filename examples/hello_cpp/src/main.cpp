/*
 * hello_cpp - KOS C++ Application
 * 
 * This is a template KOS application written in C++.
 */

#include <iostream>
#include <string>
#include <vector>
#include <memory>

// KOS API headers (when available)
// #include <kos/api.hpp>
// #include <kos/system.hpp>

// Application headers
#include "hello_cpp.hpp"

using namespace std;

// Application class
class hello_cppApp {
private:
    string appName;
    string version;
    bool debugMode;
    
public:
    hello_cppApp() : appName("hello_cpp"), version("1.0.0"), debugMode(false) {}
    
    void printBanner() {
        cout << appName << " - KOS C++ Application" << endl;
        cout << "============================" << endl << endl;
    }
    
    int run(int argc, char* argv[]) {
        // Process arguments
        if (!processArguments(argc, argv)) {
            return 1;
        }
        
        // Initialize KOS runtime (when available)
        // kos::Runtime::initialize();
        
        // Your application logic here
        cout << "Hello from " << appName << "!" << endl;
        cout << "This is a KOS C++ application template." << endl;
        
        // Example: Using KOS API
        // auto systemInfo = kos::System::getInfo();
        // cout << "KOS Version: " << systemInfo.version << endl;
        // cout << "Platform: " << systemInfo.platform << endl;
        
        // Cleanup
        // kos::Runtime::cleanup();
        
        return 0;
    }
    
private:
    bool processArguments(int argc, char* argv[]) {
        vector<string> args(argv + 1, argv + argc);
        
        for (const auto& arg : args) {
            if (arg == "-h" || arg == "--help") {
                printUsage();
                exit(0);
            } else if (arg == "-v" || arg == "--version") {
                cout << appName << " version " << version << endl;
                exit(0);
            } else if (arg == "-d" || arg == "--debug") {
                debugMode = true;
            } else {
                cerr << "Unknown option: " << arg << endl;
                printUsage();
                return false;
            }
        }
        return true;
    }
    
    void printUsage() {
        cout << "Usage: hello_cpp [options]" << endl;
        cout << "Options:" << endl;
        cout << "  -h, --help     Show this help message" << endl;
        cout << "  -v, --version  Show version information" << endl;
        cout << "  -d, --debug    Enable debug mode" << endl;
    }
};

// Main entry point
int main(int argc, char* argv[]) {
    hello_cppApp app;
    app.printBanner();
    return app.run(argc, argv);
}
