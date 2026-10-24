# Runtime library repair review

## Confirmed failure

Cloud run 2 built `twrp-lvgl-houji-2-3c65008b.img` (SHA256
`bbc5e21aede58f3988e890617d189763c23cb589d69e86ce3ed2277986b38c79`).
The failed boot log reported a linker failure in `/system/bin/init` at
5.390462 seconds, followed by `Attempted to kill init!` and a kernel panic.
The missing symbol was:

```text
_ZTVNSt3__118basic_stringstreamIcNS_11char_traitsIcEENS_9allocatorIcEEEE
```

The final ramdisk's `system/lib64/libc++.so` was the device-tree overlay,
not the Android 16 build output. It did not export this symbol.
`libc++-v35.so` did export it, but it is a differently named compatibility
library, despite also declaring `DT_SONAME=libc++.so`. Treating that file as
the default runtime library caused the earlier offline audit to miss the fault.

Phone logs remain outside this repository. No phone identifiers or full crash
archives are included here.

## Reviewed changes

- Remove only `recovery/root/system/lib64/libc++.so`. The pinned TWRP source's
  `relink_libraries` rule already installs the Android platform build's library;
  the later device overlay must not overwrite it.
- Retain `libc++-v35.so` and `libdmabufheap.so`. The latter explicitly needs
  the former, and the copied QSEE/vendor stack needs `libdmabufheap.so`.
- Reject a reintroduced default C++ overlay during input validation.
- After cloud compilation, compare the platform and staged recovery C++
  library byte-for-byte and record their hashes.
- Inspect the final packed image before uploading it. Resolve `DT_NEEDED`
  by actual filename and ramdisk paths, check strong dynamic symbols, and
  reject missing dependencies. A same-SONAME alternate must not substitute
  for a missing or incompatible default file.
- Run small ELF regression fixtures in CI. Keep the full failed image as an
  optional local negative regression, rather than committing a 100-MiB fixture.

The old `libexpat.so` overlay was raised as a separate audit concern. There is
no demonstrated expat failure in this boot log and no confirmed replacement
installation path in this build, so it is preserved in this focused repair.

## Validation boundaries

The offline checker models filename-based library search and strong-symbol
availability. It does not fully emulate Android namespaces, symbol versions,
runtime `dlopen`, SELinux, or service initialization. Duplicate SONAMEs are
reported as runtime-loading risks rather than silently merged.

The retained v35 compatibility library and the platform C++ library may both
appear in a vendor dependency graph. That existing vendor arrangement still
requires testing with the newly built image; removing or rewriting those vendor
dependencies without evidence is outside this repair.

A successful new cloud build must satisfy both the library identity check and
the packed-image checks. Boot, LVGL display/input, and Android 14–17 data
decryption remain separate device tests. No flashing or rebooting is performed
by the build or validation scripts.
