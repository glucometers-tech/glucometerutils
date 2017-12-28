# -*- python -*-

http_archive(
    name = "abseil_py_archive",
    strip_prefix = "abseil-py-9dd9c42657fee7f4022d625e39ca0f1f25ce265e",
    urls = ["https://github.com/abseil/abseil-py/archive/9dd9c42657fee7f4022d625e39ca0f1f25ce265e.zip"]
)

# From abseil-py (neeeded as transitive dependency).
# Copyright 2017 The Abseil Authors.
new_http_archive(
    name = "six_archive",
    urls = [
        "http://mirror.bazel.build/pypi.python.org/packages/source/s/six/six-1.10.0.tar.gz",
        "https://pypi.python.org/packages/source/s/six/six-1.10.0.tar.gz",
    ],
    sha256 = "105f8d68616f8248e24bf0e9372ef04d3cc10104f1980f54d57b2ce73a5ad56a",
    strip_prefix = "six-1.10.0",
    build_file = "third_party/six.BUILD",
)
