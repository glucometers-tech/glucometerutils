# -*- python -*-

package(
    default_visibility = [
        "//glucometerutils:__subpackages__",
        "//test:__pkg__",
    ]
)

py_library(
    name = "exceptions",
    srcs = ["exceptions.py"],
    srcs_version = "PY3",
)

py_library(
    name = "common",
    srcs = ["common.py"],
    srcs_version = "PY3",
    deps = [
        ":exceptions",
    ]
)
