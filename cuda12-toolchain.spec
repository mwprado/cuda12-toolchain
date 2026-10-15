%global gcc_version        14.4.0
%global glibc_version      2.40
%global gmp_version        6.2.1
%global mpfr_version       4.1.0
%global mpc_version        1.2.1
%global isl_version        0.24
%global toolchain_release  5

%global custom_gcc_root    /usr/lib64/custom-gcc14
%global custom_glibc_root  /usr/lib64/custom-glibc

Name:           cuda12-toolchain
Version:        1.0
Release:        %{toolchain_release}%{?dist}
Summary:        Bootstrap GCC 14 and glibc 2.40 toolchain for CUDA 12.9

License:        GPL-3.0-or-later AND LGPL-2.1-or-later
URL:            https://gcc.gnu.org/

Source0:        https://ftp.gnu.org/gnu/gcc/gcc-%{gcc_version}/gcc-%{gcc_version}.tar.xz
Source1:        https://ftp.gnu.org/gnu/glibc/glibc-%{glibc_version}.tar.xz
Source2:        https://gcc.gnu.org/pub/gcc/infrastructure/gmp-%{gmp_version}.tar.bz2
Source3:        https://gcc.gnu.org/pub/gcc/infrastructure/mpfr-%{mpfr_version}.tar.bz2
Source4:        https://gcc.gnu.org/pub/gcc/infrastructure/mpc-%{mpc_version}.tar.gz
Source5:        https://gcc.gnu.org/pub/gcc/infrastructure/isl-%{isl_version}.tar.bz2

ExclusiveArch:  x86_64

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  glibc-devel
BuildRequires:  binutils
BuildRequires:  bzip2
BuildRequires:  gzip
BuildRequires:  make
BuildRequires:  bison
BuildRequires:  flex
BuildRequires:  gawk
BuildRequires:  grep
BuildRequires:  sed
BuildRequires:  diffutils
BuildRequires:  findutils
BuildRequires:  python3
BuildRequires:  perl
BuildRequires:  texinfo
BuildRequires:  kernel-headers
BuildRequires:  gmp-devel
BuildRequires:  mpfr-devel
BuildRequires:  libmpc-devel
BuildRequires:  isl-devel
%if 0%{?rhel} == 9
BuildRequires:  zlib-devel
%else
BuildRequires:  zlib-ng-compat-devel
%endif

%global debug_package %{nil}
%global _debugsource_packages 0

%description
Bootstrap-only source package used to build a private GCC 14.4 and
glibc 2.40 toolchain for CUDA 12.x. Installed files are emitted only
by the custom-gcc14 and custom-glibc subpackages.

%package -n custom-gcc14
Version:        %{gcc_version}
Release:        %{toolchain_release}%{?dist}
Summary:        GCC 14.4 toolchain built against private glibc 2.40
License:        GPL-3.0-or-later WITH GCC-exception-3.1
AutoProv:       no
Requires:       custom-glibc = %{glibc_version}-%{toolchain_release}%{?dist}

%description -n custom-gcc14
Private GCC 14.4 toolchain intended for CUDA 12.x.
The target runtime libraries are built against the private glibc 2.40
sysroot installed in %{custom_glibc_root}.
The compiler is installed in %{custom_gcc_root} and does not replace
the Fedora system compiler.

%package -n custom-glibc
Version:        %{glibc_version}
Release:        %{toolchain_release}%{?dist}
Summary:        Private glibc 2.40 sysroot for CUDA 12.x
License:        LGPL-2.1-or-later
AutoReqProv:    no

%description -n custom-glibc
Private GNU C Library 2.40 sysroot intended for the CUDA 12.x
compatibility toolchain.
It contains glibc headers, libraries, startup objects and Linux UAPI
headers beneath %{custom_glibc_root}.
It does not replace or modify the Fedora system glibc.

%prep
%setup -q -c -T

tar -xf %{SOURCE0}
tar -xf %{SOURCE1}
tar -xf %{SOURCE2}
tar -xf %{SOURCE3}
tar -xf %{SOURCE4}
tar -xf %{SOURCE5}

%build
set -e

TOP="$(pwd)"

GCC_SRC="${TOP}/gcc-%{gcc_version}"
GLIBC_SRC="${TOP}/glibc-%{glibc_version}"
GMP_SRC="${TOP}/gmp-%{gmp_version}"
MPFR_SRC="${TOP}/mpfr-%{mpfr_version}"
MPC_SRC="${TOP}/mpc-%{mpc_version}"
ISL_SRC="${TOP}/isl-%{isl_version}"

STAGE0_GCC="${TOP}/stage0-gcc14"
STAGE1_GLIBC="${TOP}/stage1-glibc"
STAGE2_GCC="${TOP}/stage2-gcc14"
STAGE3_GLIBC="${TOP}/stage3-glibc"

GCC_BUILD0="${TOP}/build-gcc-stage0"
GLIBC_BUILD1="${TOP}/build-glibc-stage1"
GCC_BUILD2="${TOP}/build-gcc-stage2"
GLIBC_BUILD3="${TOP}/build-glibc-stage3"

STAGE35_DEPS="${TOP}/stage35-deps"
GMP_BUILD35="${TOP}/build-gmp-stage35"
MPFR_BUILD35="${TOP}/build-mpfr-stage35"
MPC_BUILD35="${TOP}/build-mpc-stage35"
ISL_BUILD35="${TOP}/build-isl-stage35"

GCC_BUILD4="${TOP}/build-gcc-stage4"
STAGE4_ROOT="${TOP}/stage4-root"

FINAL_GCC_ROOT="%{custom_gcc_root}"
FINAL_GLIBC_ROOT="%{custom_glibc_root}"

JOBS="$(nproc)"

export CFLAGS="-O2 -g"
export CXXFLAGS="-O2 -g"
export LDFLAGS=""

unset FFLAGS || :
unset FCFLAGS || :

fatal()
{
    echo "" >&2
    echo "============================================================" >&2
    echo "ERROR: $*" >&2
    echo "============================================================" >&2
    exit 1
}

run_or_die()
{
    DESC="$1"
    shift

    echo ""
    echo ">>> ${DESC}"

    if "$@"; then
        return 0
    else
        RC=$?
        echo "" >&2
        echo "============================================================" >&2
        echo "ERROR: ${DESC} failed with exit code ${RC}" >&2
        echo "============================================================" >&2
        exit "$RC"
    fi
}

require_file()
{
    test -f "$1" || fatal "missing file: $1"
}

require_path()
{
    test -e "$1" || fatal "missing path: $1"
}

require_exec()
{
    test -x "$1" || fatal "missing executable: $1"
}

require_find()
{
    ROOT="$1"
    PATTERN="$2"
    FOUND="$(find "$ROOT" -name "$PATTERN" -print -quit 2>/dev/null)"
    test -n "$FOUND" || fatal "cannot find ${PATTERN} under ${ROOT}"
    echo "    found: ${FOUND}"
}

copy_kernel_uapi()
{
    SYSROOT="$1"

    rpm -ql kernel-headers | while IFS= read -r P; do
        case "$P" in
            /usr/include/*)
                if [ -d "$P" ] && [ ! -L "$P" ]; then
                    mkdir -p "${SYSROOT}${P}"
                elif [ -e "$P" ] || [ -L "$P" ]; then
                    mkdir -p "${SYSROOT}$(dirname "$P")"
                    cp -a "$P" "${SYSROOT}${P}"
                fi
                ;;
        esac
    done
}

check_gcc_version()
{
    CC_BIN="$1"
    EXPECTED="$2"
    ACTUAL="$($CC_BIN -dumpfullversion)"
    echo "    compiler version: ${ACTUAL}"
    test "$ACTUAL" = "$EXPECTED" || fatal "expected GCC ${EXPECTED}, got ${ACTUAL} from ${CC_BIN}"
}

check_stage0_gcc()
{
    echo ">>> CHECK stage0 GCC"

    require_exec "$STAGE0_GCC/bin/gcc"
    check_gcc_version "$STAGE0_GCC/bin/gcc" "%{gcc_version}"

    LIBGCC="$($STAGE0_GCC/bin/gcc -print-libgcc-file-name)"
    require_file "$LIBGCC"

    cat > "$TOP/check-stage0.c" <<'EOF'
int main(void) { return 0; }
EOF

    run_or_die "stage0 C compile/link smoke test" \
        "$STAGE0_GCC/bin/gcc" \
        "$TOP/check-stage0.c" \
        -o "$TOP/check-stage0"

    require_exec "$TOP/check-stage0"

    echo "=== stage0 CHECK OK ==="
}

check_glibc_tree()
{
    TAG="$1"
    SYSROOT="$2"

    echo ">>> CHECK ${TAG} glibc tree"

    require_file "$SYSROOT/usr/include/features.h"
    require_file "$SYSROOT/usr/include/pthread.h"
    require_file "$SYSROOT/usr/include/linux/limits.h"
    require_path "$SYSROOT/usr/include/asm"
    require_path "$SYSROOT/usr/include/asm-generic"

    require_path "$SYSROOT/lib64/libc.so.6"
    require_path "$SYSROOT/lib64/ld-linux-x86-64.so.2"

    require_file "$SYSROOT/usr/lib64/crt1.o"
    require_file "$SYSROOT/usr/lib64/crti.o"
    require_file "$SYSROOT/usr/lib64/crtn.o"

    LOADER_VERSION="$($SYSROOT/lib64/ld-linux-x86-64.so.2 --version | head -n 1)"
    echo "    loader: ${LOADER_VERSION}"
    echo "$LOADER_VERSION" | grep -q '%{glibc_version}' || fatal "${TAG}: loader is not glibc %{glibc_version}"
}

check_c_sysroot_link()
{
    TAG="$1"
    CC_BIN="$2"
    SYSROOT="$3"

    cat > "$TOP/check-${TAG}.c" <<'EOF'
#include <pthread.h>
#include <math.h>
int main(void)
{
    pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
    return (sizeof(cond) == 0) || (cos(0.0) != 1.0);
}
EOF

    run_or_die "${TAG} C sysroot compile/link test" \
        "$CC_BIN" \
        --sysroot="$SYSROOT" \
        -B"$SYSROOT/usr/lib64/" \
        "$TOP/check-${TAG}.c" \
        -lm \
        -o "$TOP/check-${TAG}-c"

    require_exec "$TOP/check-${TAG}-c"

    CRT="$($CC_BIN --sysroot="$SYSROOT" -B"$SYSROOT/usr/lib64/" -print-file-name=crti.o)"
    echo "    crti.o resolved as: ${CRT}"
    test "$CRT" != "crti.o" || fatal "${TAG}: compiler cannot resolve crti.o"
    require_file "$CRT"
}

check_complete_gcc()
{
    TAG="$1"
    GCC_ROOT="$2"
    SYSROOT="$3"

    echo ">>> CHECK ${TAG} complete GCC"

    require_exec "$GCC_ROOT/bin/gcc"
    require_exec "$GCC_ROOT/bin/g++"
    check_gcc_version "$GCC_ROOT/bin/gcc" "%{gcc_version}"
    check_gcc_version "$GCC_ROOT/bin/g++" "%{gcc_version}"

    require_find "$GCC_ROOT" 'libgcc_s.so.1'
    require_find "$GCC_ROOT" 'libstdc++.so.6*'

    cat > "$TOP/check-${TAG}.cpp" <<'EOF'
#include <mutex>
#include <condition_variable>
int main()
{
    std::mutex m;
    std::condition_variable cv;
    return sizeof(m) == 0 || sizeof(cv) == 0;
}
EOF

    run_or_die "${TAG} C++ sysroot compile/link test" \
        "$GCC_ROOT/bin/g++" \
        --sysroot="$SYSROOT" \
        -B"$SYSROOT/usr/lib64/" \
        "$TOP/check-${TAG}.cpp" \
        -o "$TOP/check-${TAG}-cpp"

    require_exec "$TOP/check-${TAG}-cpp"

    CRT="$($GCC_ROOT/bin/g++ --sysroot="$SYSROOT" -B"$SYSROOT/usr/lib64/" -print-file-name=crti.o)"
    echo "    crti.o resolved as: ${CRT}"
    test "$CRT" != "crti.o" || fatal "${TAG}: g++ cannot resolve crti.o"
    require_file "$CRT"

    echo "=== ${TAG} CHECK OK ==="
}

# ============================================================
# stage0: GCC 14 C-only + libgcc
# ============================================================

echo "=== stage0: GCC %{gcc_version} C-only bootstrap ==="

rm -rf "$GCC_BUILD0" "$STAGE0_GCC"
mkdir -p "$GCC_BUILD0" "$STAGE0_GCC"

pushd "$GCC_BUILD0"

run_or_die "stage0 GCC configure" \
    "$GCC_SRC/configure" \
    --prefix="$STAGE0_GCC" \
    --enable-languages=c \
    --disable-bootstrap \
    --disable-multilib \
    --disable-nls

run_or_die "stage0 all-gcc" \
    make -j"$JOBS" all-gcc

run_or_die "stage0 all-target-libgcc" \
    make -j"$JOBS" all-target-libgcc

run_or_die "stage0 install-gcc" \
    make install-gcc

run_or_die "stage0 install-target-libgcc" \
    make install-target-libgcc

popd

check_stage0_gcc

# ============================================================
# stage1: first glibc 2.40 built by stage0 GCC14
# ============================================================

echo "=== stage1: glibc %{glibc_version} bootstrap ==="

rm -rf "$GLIBC_BUILD1" "$STAGE1_GLIBC"
mkdir -p "$GLIBC_BUILD1" "$STAGE1_GLIBC"

pushd "$GLIBC_BUILD1"

run_or_die "stage1 glibc configure" \
    env \
    CC="$STAGE0_GCC/bin/gcc" \
    BUILD_CC=/usr/bin/gcc \
    CFLAGS="-O2 -g" \
    LDFLAGS="" \
    "$GLIBC_SRC/configure" \
    --prefix=/usr \
    --libdir=/usr/lib64 \
    --includedir=/usr/include \
    --disable-werror

run_or_die "stage1 glibc build" \
    make -j"$JOBS"

run_or_die "stage1 glibc install" \
    make install install_root="$STAGE1_GLIBC"

popd

copy_kernel_uapi "$STAGE1_GLIBC"

rm -f "$STAGE1_GLIBC/etc/ld.so.cache"
rm -f "$STAGE1_GLIBC/etc/ld.so.conf"

check_glibc_tree "stage1" "$STAGE1_GLIBC"
check_c_sysroot_link "stage1" "$STAGE0_GCC/bin/gcc" "$STAGE1_GLIBC"
echo "=== stage1 CHECK OK ==="

# ============================================================
# stage2: first complete GCC14 against stage1 glibc 2.40
# ============================================================

echo "=== stage2: complete GCC %{gcc_version} ==="

rm -rf "$GCC_BUILD2" "$STAGE2_GCC"
mkdir -p "$GCC_BUILD2" "$STAGE2_GCC"

pushd "$GCC_BUILD2"

run_or_die "stage2 GCC configure" \
    env \
    CC=/usr/bin/gcc \
    CXX=/usr/bin/g++ \
    CFLAGS="-O2 -g" \
    CXXFLAGS="-O2 -g" \
    LDFLAGS="" \
    "$GCC_SRC/configure" \
    --prefix="$STAGE2_GCC" \
    --with-sysroot="$FINAL_GLIBC_ROOT" \
    --with-build-sysroot="$STAGE1_GLIBC" \
    --with-native-system-header-dir=/usr/include \
    --with-glibc-version=%{glibc_version} \
    --enable-languages=c,c++ \
    --disable-bootstrap \
    --disable-multilib \
    --disable-libssp \
    --disable-libquadmath \
    --disable-libgomp \
    --disable-libatomic \
    --disable-libsanitizer \
    --disable-nls

run_or_die "stage2 all-gcc" \
    make -j"$JOBS" all-gcc

run_or_die "stage2 all-target-libgcc" \
    make -j"$JOBS" all-target-libgcc \
    CFLAGS_FOR_TARGET="-O2 -g -B$STAGE1_GLIBC/usr/lib64/" \
    CXXFLAGS_FOR_TARGET="-O2 -g -B$STAGE1_GLIBC/usr/lib64/" \
    LDFLAGS_FOR_TARGET="-B$STAGE1_GLIBC/usr/lib64/"

run_or_die "stage2 all-target-libstdc++-v3" \
    make -j"$JOBS" all-target-libstdc++-v3 \
    CFLAGS_FOR_TARGET="-O2 -g -B$STAGE1_GLIBC/usr/lib64/" \
    CXXFLAGS_FOR_TARGET="-O2 -g -B$STAGE1_GLIBC/usr/lib64/" \
    LDFLAGS_FOR_TARGET="-B$STAGE1_GLIBC/usr/lib64/"

run_or_die "stage2 install-gcc" \
    make install-gcc

run_or_die "stage2 install-target-libgcc" \
    make install-target-libgcc

run_or_die "stage2 install-target-libstdc++-v3" \
    make install-target-libstdc++-v3

popd

check_complete_gcc "stage2" "$STAGE2_GCC" "$STAGE1_GLIBC"
check_c_sysroot_link "stage2" "$STAGE2_GCC/bin/gcc" "$STAGE1_GLIBC"
echo "=== stage2 CHECK OK ==="

# ============================================================
# stage3: rebuild glibc 2.40 with complete stage2 GCC14
# ============================================================

echo "=== stage3: final glibc %{glibc_version} ==="

rm -rf "$GLIBC_BUILD3" "$STAGE3_GLIBC"
mkdir -p "$GLIBC_BUILD3" "$STAGE3_GLIBC"

pushd "$GLIBC_BUILD3"

run_or_die "stage3 glibc configure" \
    env \
    CC="$STAGE2_GCC/bin/gcc --sysroot=$STAGE1_GLIBC -B$STAGE1_GLIBC/usr/lib64/" \
    BUILD_CC=/usr/bin/gcc \
    CFLAGS="-O2 -g" \
    LDFLAGS="" \
    "$GLIBC_SRC/configure" \
    --prefix=/usr \
    --libdir=/usr/lib64 \
    --includedir=/usr/include \
    --disable-werror

run_or_die "stage3 glibc build" \
    make -j"$JOBS"

run_or_die "stage3 glibc install" \
    make install install_root="$STAGE3_GLIBC"

popd

copy_kernel_uapi "$STAGE3_GLIBC"

rm -f "$STAGE3_GLIBC/etc/ld.so.cache"
rm -f "$STAGE3_GLIBC/etc/ld.so.conf"

check_glibc_tree "stage3" "$STAGE3_GLIBC"
check_c_sysroot_link "stage3" "$STAGE2_GCC/bin/gcc" "$STAGE3_GLIBC"
check_complete_gcc "stage2-vs-stage3" "$STAGE2_GCC" "$STAGE3_GLIBC"
echo "=== stage3 CHECK OK ==="

# ============================================================
# stage3.5: GCC host prerequisites against final glibc 2.40
#
# These libraries are temporary bootstrap inputs.  They are built
# static-only so the final GCC does not acquire runtime dependencies
# on Fedora's GMP/MPFR/MPC/ISL shared libraries.
# ============================================================

echo "=== stage3.5: private GCC host prerequisites ==="

rm -rf \
    "$STAGE35_DEPS" \
    "$GMP_BUILD35" \
    "$MPFR_BUILD35" \
    "$MPC_BUILD35" \
    "$ISL_BUILD35"

mkdir -p \
    "$STAGE35_DEPS" \
    "$GMP_BUILD35" \
    "$MPFR_BUILD35" \
    "$MPC_BUILD35" \
    "$ISL_BUILD35"

DEPS_CC="$STAGE2_GCC/bin/gcc --sysroot=$STAGE3_GLIBC -B$STAGE3_GLIBC/usr/lib64/"
DEPS_CXX="$STAGE2_GCC/bin/g++ --sysroot=$STAGE3_GLIBC -B$STAGE3_GLIBC/usr/lib64/"

echo ">>> stage3.5 GMP %{gmp_version}"

pushd "$GMP_BUILD35"

run_or_die "stage3.5 GMP configure" \
    env \
    CC="$DEPS_CC" \
    CXX="$DEPS_CXX" \
    CFLAGS="-O2 -g -fPIC" \
    CXXFLAGS="-O2 -g -fPIC" \
    LDFLAGS="" \
    "$GMP_SRC/configure" \
    --prefix="$STAGE35_DEPS" \
    --libdir="$STAGE35_DEPS/lib" \
    --disable-shared \
    --enable-static \
    --with-pic

run_or_die "stage3.5 GMP build" \
    make -j"$JOBS"

run_or_die "stage3.5 GMP install" \
    make install

popd

require_file "$STAGE35_DEPS/include/gmp.h"
require_file "$STAGE35_DEPS/lib/libgmp.a"

echo ">>> stage3.5 MPFR %{mpfr_version}"

pushd "$MPFR_BUILD35"

run_or_die "stage3.5 MPFR configure" \
    env \
    CC="$DEPS_CC" \
    CFLAGS="-O2 -g -fPIC" \
    CPPFLAGS="-I$STAGE35_DEPS/include" \
    LDFLAGS="-L$STAGE35_DEPS/lib" \
    "$MPFR_SRC/configure" \
    --prefix="$STAGE35_DEPS" \
    --libdir="$STAGE35_DEPS/lib" \
    --with-gmp="$STAGE35_DEPS" \
    --disable-shared \
    --enable-static \
    --with-pic

run_or_die "stage3.5 MPFR build" \
    make -j"$JOBS"

run_or_die "stage3.5 MPFR install" \
    make install

popd

require_file "$STAGE35_DEPS/include/mpfr.h"
require_file "$STAGE35_DEPS/lib/libmpfr.a"

echo ">>> stage3.5 MPC %{mpc_version}"

pushd "$MPC_BUILD35"

run_or_die "stage3.5 MPC configure" \
    env \
    CC="$DEPS_CC" \
    CFLAGS="-O2 -g -fPIC" \
    CPPFLAGS="-I$STAGE35_DEPS/include" \
    LDFLAGS="-L$STAGE35_DEPS/lib" \
    "$MPC_SRC/configure" \
    --prefix="$STAGE35_DEPS" \
    --libdir="$STAGE35_DEPS/lib" \
    --with-gmp="$STAGE35_DEPS" \
    --with-mpfr="$STAGE35_DEPS" \
    --disable-shared \
    --enable-static \
    --with-pic

run_or_die "stage3.5 MPC build" \
    make -j"$JOBS"

run_or_die "stage3.5 MPC install" \
    make install

popd

require_file "$STAGE35_DEPS/include/mpc.h"
require_file "$STAGE35_DEPS/lib/libmpc.a"

echo ">>> stage3.5 ISL %{isl_version}"

pushd "$ISL_BUILD35"

run_or_die "stage3.5 ISL configure" \
    env \
    CC="$DEPS_CC" \
    CXX="$DEPS_CXX" \
    CFLAGS="-O2 -g -fPIC" \
    CXXFLAGS="-O2 -g -fPIC" \
    CPPFLAGS="-I$STAGE35_DEPS/include" \
    LDFLAGS="-L$STAGE35_DEPS/lib" \
    "$ISL_SRC/configure" \
    --prefix="$STAGE35_DEPS" \
    --libdir="$STAGE35_DEPS/lib" \
    --with-gmp-prefix="$STAGE35_DEPS" \
    --disable-shared \
    --enable-static \
    --with-pic

run_or_die "stage3.5 ISL build" \
    make -j"$JOBS"

run_or_die "stage3.5 ISL install" \
    make install

popd

require_file "$STAGE35_DEPS/include/isl/ctx.h"
require_file "$STAGE35_DEPS/lib/libisl.a"

cat > "$TOP/check-stage35.c" <<'EOF'
#include <gmp.h>
#include <mpfr.h>
#include <mpc.h>
#include <isl/ctx.h>

int main(void)
{
    mpz_t z;
    mpfr_t r;
    mpc_t c;
    isl_ctx *ctx;

    mpz_init_set_ui(z, 1);
    mpfr_init2(r, 64);
    mpc_init2(c, 64);
    ctx = isl_ctx_alloc();

    if (!ctx)
        return 1;

    isl_ctx_free(ctx);
    mpc_clear(c);
    mpfr_clear(r);
    mpz_clear(z);

    return 0;
}
EOF

run_or_die "stage3.5 prerequisite compile/link smoke test" \
    "$STAGE2_GCC/bin/gcc" \
    --sysroot="$STAGE3_GLIBC" \
    -B"$STAGE3_GLIBC/usr/lib64/" \
    -I"$STAGE35_DEPS/include" \
    "$TOP/check-stage35.c" \
    "$STAGE35_DEPS/lib/libisl.a" \
    "$STAGE35_DEPS/lib/libmpc.a" \
    "$STAGE35_DEPS/lib/libmpfr.a" \
    "$STAGE35_DEPS/lib/libgmp.a" \
    -lm \
    -o "$TOP/check-stage35"

require_exec "$TOP/check-stage35"

echo "=== stage3.5 CHECK OK ==="

# ============================================================
# stage4: final GCC14 against stage3 glibc 2.40
# ============================================================

echo "=== stage4: final GCC %{gcc_version} ==="

rm -rf "$GCC_BUILD4" "$STAGE4_ROOT"
mkdir -p "$GCC_BUILD4" "$STAGE4_ROOT"

pushd "$GCC_BUILD4"

# Keep the stage2 C++ runtime available while configure executes its
# temporary host test programs.  Do not add the private glibc itself to
# LD_LIBRARY_PATH; compile-time selection is controlled by --sysroot.
export LD_LIBRARY_PATH="$STAGE2_GCC/lib64:$STAGE2_GCC/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

run_or_die "stage4 GCC configure" \
    env \
    CC="$STAGE2_GCC/bin/gcc --sysroot=$STAGE3_GLIBC -B$STAGE3_GLIBC/usr/lib64/" \
    CXX="$STAGE2_GCC/bin/g++ --sysroot=$STAGE3_GLIBC -B$STAGE3_GLIBC/usr/lib64/" \
    CPPFLAGS="-I$STAGE35_DEPS/include" \
    CFLAGS="-O2 -g" \
    CXXFLAGS="-O2 -g" \
    LDFLAGS="-L$STAGE35_DEPS/lib" \
    "$GCC_SRC/configure" \
    --prefix="$FINAL_GCC_ROOT" \
    --with-sysroot="$FINAL_GLIBC_ROOT" \
    --with-build-sysroot="$STAGE3_GLIBC" \
    --with-native-system-header-dir=/usr/include \
    --with-glibc-version=%{glibc_version} \
    --with-gmp="$STAGE35_DEPS" \
    --with-mpfr="$STAGE35_DEPS" \
    --with-mpc="$STAGE35_DEPS" \
    --with-isl="$STAGE35_DEPS" \
    --without-zstd \
    --enable-languages=c,c++ \
    --disable-bootstrap \
    --disable-multilib \
    --disable-libssp \
    --disable-libquadmath \
    --disable-libgomp \
    --disable-libatomic \
    --disable-libsanitizer \
    --disable-nls

run_or_die "stage4 all-gcc" \
    make -j"$JOBS" all-gcc

run_or_die "stage4 all-target-libgcc" \
    make -j"$JOBS" all-target-libgcc \
    CFLAGS_FOR_TARGET="-O2 -g -B$STAGE3_GLIBC/usr/lib64/" \
    CXXFLAGS_FOR_TARGET="-O2 -g -B$STAGE3_GLIBC/usr/lib64/" \
    LDFLAGS_FOR_TARGET="-B$STAGE3_GLIBC/usr/lib64/"

run_or_die "stage4 all-target-libstdc++-v3" \
    make -j"$JOBS" all-target-libstdc++-v3 \
    CFLAGS_FOR_TARGET="-O2 -g -B$STAGE3_GLIBC/usr/lib64/" \
    CXXFLAGS_FOR_TARGET="-O2 -g -B$STAGE3_GLIBC/usr/lib64/" \
    LDFLAGS_FOR_TARGET="-B$STAGE3_GLIBC/usr/lib64/"

run_or_die "stage4 staged install-gcc" \
    make DESTDIR="$STAGE4_ROOT" install-gcc

run_or_die "stage4 staged install-target-libgcc" \
    make DESTDIR="$STAGE4_ROOT" install-target-libgcc

run_or_die "stage4 staged install-target-libstdc++-v3" \
    make DESTDIR="$STAGE4_ROOT" install-target-libstdc++-v3

popd

STAGE4_GCC="$STAGE4_ROOT$FINAL_GCC_ROOT"

require_exec "$STAGE4_GCC/bin/gcc"
require_exec "$STAGE4_GCC/bin/g++"
check_gcc_version "$STAGE4_GCC/bin/gcc" "%{gcc_version}"
check_gcc_version "$STAGE4_GCC/bin/g++" "%{gcc_version}"
require_find "$STAGE4_GCC" 'libgcc_s.so.1'
require_find "$STAGE4_GCC" 'libstdc++.so.6*'

STAGE4_SYSROOT="$($STAGE4_GCC/bin/gcc -print-sysroot)"
echo "    final GCC configured sysroot: ${STAGE4_SYSROOT}"
test "$STAGE4_SYSROOT" = "$FINAL_GLIBC_ROOT" || fatal "stage4 GCC has wrong configured sysroot: ${STAGE4_SYSROOT}"

echo "=== stage4 CHECK OK ==="

%install
set -e

TOP="$(pwd)"
STAGE3_GLIBC="${TOP}/stage3-glibc"
STAGE4_ROOT="${TOP}/stage4-root"

rm -rf %{buildroot}%{custom_gcc_root}
rm -rf %{buildroot}%{custom_glibc_root}
rm -rf %{buildroot}%{_libexecdir}/custom-gcc14

mkdir -p %{buildroot}%{custom_glibc_root}
mkdir -p %{buildroot}%{custom_gcc_root}

cp -a "$STAGE3_GLIBC"/. %{buildroot}%{custom_glibc_root}/
cp -a "$STAGE4_ROOT%{custom_gcc_root}"/. %{buildroot}%{custom_gcc_root}/

mkdir -p %{buildroot}%{_libexecdir}/custom-gcc14

cat > %{buildroot}%{_libexecdir}/custom-gcc14/env.sh <<'EOF'
CUSTOM_GCC14_ROOT=/usr/lib64/custom-gcc14
CUSTOM_GLIBC_ROOT=/usr/lib64/custom-glibc

export CUSTOM_GCC14_ROOT
export CUSTOM_GLIBC_ROOT

export CC="${CUSTOM_GCC14_ROOT}/bin/gcc"
export CXX="${CUSTOM_GCC14_ROOT}/bin/g++"
export PATH="${CUSTOM_GCC14_ROOT}/bin:${PATH}"
EOF

chmod 0755 %{buildroot}%{_libexecdir}/custom-gcc14/env.sh

rm -f %{buildroot}%{custom_glibc_root}/etc/ld.so.cache
rm -f %{buildroot}%{custom_glibc_root}/etc/ld.so.conf

%check
set -e

fatal_check()
{
    echo "ERROR: final package check: $*" >&2
    exit 1
}

test -f %{buildroot}%{custom_glibc_root}/usr/include/features.h || fatal_check "features.h missing"
test -f %{buildroot}%{custom_glibc_root}/usr/include/pthread.h || fatal_check "pthread.h missing"
test -f %{buildroot}%{custom_glibc_root}/usr/include/linux/limits.h || fatal_check "linux/limits.h missing"

test -e %{buildroot}%{custom_glibc_root}/lib64/libc.so.6 || fatal_check "libc.so.6 missing"
test -e %{buildroot}%{custom_glibc_root}/lib64/ld-linux-x86-64.so.2 || fatal_check "dynamic loader missing"

test -f %{buildroot}%{custom_glibc_root}/usr/lib64/crt1.o || fatal_check "crt1.o missing"
test -f %{buildroot}%{custom_glibc_root}/usr/lib64/crti.o || fatal_check "crti.o missing"
test -f %{buildroot}%{custom_glibc_root}/usr/lib64/crtn.o || fatal_check "crtn.o missing"

test -x %{buildroot}%{custom_gcc_root}/bin/gcc || fatal_check "gcc missing"
test -x %{buildroot}%{custom_gcc_root}/bin/g++ || fatal_check "g++ missing"

test "$(%{buildroot}%{custom_gcc_root}/bin/gcc -dumpfullversion)" = "%{gcc_version}" || fatal_check "wrong GCC version"
test "$(%{buildroot}%{custom_gcc_root}/bin/gcc -print-sysroot)" = "%{custom_glibc_root}" || fatal_check "wrong configured GCC sysroot"

CRT1="$(
    %{buildroot}%{custom_gcc_root}/bin/gcc \
        --sysroot=%{buildroot}%{custom_glibc_root} \
        -B%{buildroot}%{custom_glibc_root}/usr/lib64/ \
        -print-file-name=crt1.o
)"

echo "final crt1.o resolved as: $CRT1"
test "$CRT1" != "crt1.o" || fatal_check "final GCC cannot resolve crt1.o"
test -f "$CRT1" || fatal_check "resolved crt1.o does not exist"

cat > final-cxx-check.cpp <<'EOF'
#include <mutex>
#include <condition_variable>
int main()
{
    std::mutex m;
    std::condition_variable cv;
    return sizeof(m) == 0 || sizeof(cv) == 0;
}
EOF

%{buildroot}%{custom_gcc_root}/bin/g++ \
    --sysroot=%{buildroot}%{custom_glibc_root} \
    -B%{buildroot}%{custom_glibc_root}/usr/lib64/ \
    final-cxx-check.cpp \
    -o final-cxx-check || fatal_check "final C++ sysroot compile/link failed"

test -x final-cxx-check || fatal_check "final C++ test binary not generated"

echo "=== FINAL TOOLCHAIN CHECK OK ==="

%files -n custom-gcc14
%{custom_gcc_root}
%{_libexecdir}/custom-gcc14

%files -n custom-glibc
%{custom_glibc_root}

%changelog
* Wed Sep 16 2026 Moacyr Prado <builder@localhost> - 1.0-5
- Add GCC 14.4 canonical GMP, MPFR, MPC and ISL prerequisite sources
- Build private static prerequisite libraries as stage3.5 against glibc 2.40
- Self-host stage4 with stage2 GCC using the stage3 glibc 2.40 sysroot
- Link stage4 host tools against private static prerequisite libraries
- Disable zstd in stage4 to avoid another host-library dependency
- Add explicit stage3.5 archive/header and compile-link checks

* Wed Sep 16 2026 Moacyr Prado <builder@localhost> - 1.0-4
- Build only GCC, libgcc and libstdc++ target components in stages 2 and 4
- Do not build libssp, libquadmath, libgomp, libatomic or libsanitizer
- Keep per-component fail-fast checks so the exact failing runtime is visible
- Preserve private glibc CRT search path while building libgcc/libstdc++

* Wed Sep 16 2026 Moacyr Prado <builder@localhost> - 1.0-3
- Add explicit fail-fast validation after every bootstrap stage
- Add C and C++ sysroot compile/link smoke tests
- Verify GCC/glibc versions, CRT resolution and runtime libraries
- Add stage1/stage3 pthread header consistency checks
- Pass private sysroot usr/lib64 through -B while building target GCC runtimes
- Stage-install final GCC so stage4 can be validated before packaging

* Tue Sep 15 2026 Moacyr Prado <builder@localhost> - 1.0-2
- Align build dependencies with previously working GCC14 build
- Remove invalid zstd-devel dependency
- Add main package description
- Preserve conservative bootstrap flags
- Use actual RPM build working directory during install

* Tue Sep 15 2026 Moacyr Prado <builder@localhost> - 1.0-1
- Initial unified CUDA 12 compatibility toolchain bootstrap
