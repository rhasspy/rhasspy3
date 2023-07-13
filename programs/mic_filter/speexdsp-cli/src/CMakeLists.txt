cmake_minimum_required(VERSION 3.13)

project(raven C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig)
pkg_check_modules(SPEEXDSP REQUIRED speexdsp)

ADD_EXECUTABLE(speexdsp-cli main.cpp)

string(APPEND CMAKE_CXX_FLAGS " -Wall -Wextra")
string(APPEND CMAKE_C_FLAGS " -Wall -Wextra")

target_link_libraries(speexdsp-cli
                      ${SPEEXDSP_LIBRARIES} -static)

target_link_directories(speexdsp-cli PUBLIC
                        ${SPEEXDSP_LIBRARY_DIRS})

target_include_directories(speexdsp-cli PUBLIC
                           ${SPEEXDSP_INCLUDE_DIRS})

target_compile_options(speexdsp-cli PUBLIC
                       ${SPEEXDSP_CFLAGS_OTHER})
