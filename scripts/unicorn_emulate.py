#!/usr/bin/env python3
"""
unicorn_emulate.py — run a single native (arm64) function offline to recover a
sign/encrypt transform without the device. Reference harness; fill the TODOs from
your Ghidra/r2 analysis. See references/super-hard.md §E.

pip install unicorn capstone
Validate the output against ONE real on-device sample before trusting it.
"""
from unicorn import *
from unicorn.arm64_const import *
import struct

SO_PATH   = "libTarget.so"     # TODO: extracted .so (arm64-v8a)
LOAD_BASE = 0x0                 # TODO: base you map the file at (keep consistent with offsets)
FUNC_OFF  = 0x0                 # TODO: file offset of the target function
STACK     = 0x7000000
STACK_SZ  = 0x100000
INPUT_AT  = 0x200000           # scratch buffers
OUTPUT_AT = 0x300000
SENTINEL  = 0xDEADF00D         # LR; emulation stops here

def load_so():
    data = open(SO_PATH, "rb").read()
    return data

def hook_unmapped(uc, access, address, size, value, user):
    # Log + lazily map so you SEE what the function reads (supply traced values here).
    page = address & ~0xFFF
    try:
        uc.mem_map(page, 0x1000)
        print(f"[map-on-demand] {hex(page)} (was reading {hex(address)})")
        return True
    except Exception:
        print(f"[unmapped FAIL] {hex(address)} size={size}")
        return False

# Stub imported libc calls the function makes (return sane values).
STUBS = {
    # address_of_PLT_entry : python_callback(uc)->None (set x0 as return)
}
def make_stub(name):
    def cb(uc):
        if name == "malloc":
            sz = uc.reg_read(UC_ARM64_REG_X0); uc.reg_write(UC_ARM64_REG_X0, OUTPUT_AT)
        elif name in ("strlen",):
            uc.reg_write(UC_ARM64_REG_X0, 0x20)
        else:
            uc.reg_write(UC_ARM64_REG_X0, 0)
        print(f"[stub] {name}()")
    return cb

def hook_code(uc, address, size, user):
    if address in STUBS:
        STUBS[address](uc)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))  # ret

def emulate(input_bytes):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    blob = load_so()
    # crude full-file map (refine to PT_LOAD segments for real targets)
    size = (len(blob) + 0xFFF) & ~0xFFF
    uc.mem_map(LOAD_BASE, max(size, 0x1000))
    uc.mem_write(LOAD_BASE, blob)
    uc.mem_map(STACK, STACK_SZ)
    uc.mem_map(INPUT_AT, 0x1000); uc.mem_map(OUTPUT_AT, 0x1000)
    uc.mem_write(INPUT_AT, input_bytes)

    uc.reg_write(UC_ARM64_REG_SP, STACK + STACK_SZ - 0x100)
    uc.reg_write(UC_ARM64_REG_X0, INPUT_AT)          # TODO: arg layout per the real signature
    uc.reg_write(UC_ARM64_REG_X1, len(input_bytes))
    uc.reg_write(UC_ARM64_REG_X2, OUTPUT_AT)
    uc.reg_write(UC_ARM64_REG_LR, SENTINEL)

    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED, hook_unmapped)
    uc.hook_add(UC_HOOK_CODE, hook_code)

    try:
        uc.emu_start(LOAD_BASE + FUNC_OFF, SENTINEL)
    except UcError as e:
        print(f"[emu stopped] {e} pc={hex(uc.reg_read(UC_ARM64_REG_PC))}")
    return uc.mem_read(OUTPUT_AT, 0x40)

if __name__ == "__main__":
    out = emulate(b"hello-known-plaintext")
    print("output:", out.hex())
