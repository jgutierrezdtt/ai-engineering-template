"""Apply process limits in a fresh interpreter before replacing it with a command."""

import os
import resource
import sys


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    if len(sys.argv) < 2:
        sys.exit(2)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
