# -*- coding: utf-8 -*-
"""EggParty indice_encrypt=3 的 mode3 解密实现。"""

from __future__ import annotations

import struct

from .eggparty_mode3_tables import (
    AES_INV_SBOX,
    AES_KEYEXP_MIXCOL_TABLE,
    AES_SBOX_WORD_TABLE,
    AES_KEYEXP_ROTWORD_TABLE,
    AES_KEYEXP_T0,
    AES_DEC_T0,
    AES_DEC_T1,
    AES_DEC_T2,
    AES_DEC_T3,
)

EGGPARTY_MODE3_INDEX_KEY = bytes.fromhex("98 6E 6F 8D 30 82 4C DF F1 47 45 DA 94 68 55 EA")


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def ror32(value: int, bits: int) -> int:
    value &= 0xFFFFFFFF
    return ((value >> bits) | ((value << (32 - bits)) & 0xFFFFFFFF)) & 0xFFFFFFFF


def rol32(value: int, bits: int) -> int:
    value &= 0xFFFFFFFF
    return (((value << bits) & 0xFFFFFFFF) | (value >> (32 - bits))) & 0xFFFFFFFF


def byte0(value: int) -> int:
    return value & 0xFF


def byte1(value: int) -> int:
    return (value >> 8) & 0xFF


def byte2(value: int) -> int:
    return (value >> 16) & 0xFF


def byte3(value: int) -> int:
    return (value >> 24) & 0xFF


def swap32_neox_style(value: int) -> int:
    rotated = ror32(value, 8)
    return u32(rotated ^ ((rotated ^ rol32(value, 8)) & 0x00FF00FF))


AES_SBOX = [word & 0xFF for word in AES_SBOX_WORD_TABLE]


def build_mode3_encrypt_round_keys(key16: bytes) -> list[int]:
    """构造 mode3 使用的 128-bit 加密方向轮密钥。"""
    if len(key16) != 16:
        raise ValueError("key16 必须正好 16 字节")

    key_words = list(struct.unpack("<4I", key16))
    round_keys = [0] * 61
    round_keys[60] = 10

    round_keys[0] = swap32_neox_style(key_words[0])
    round_keys[1] = swap32_neox_style(key_words[1])
    round_keys[2] = swap32_neox_style(key_words[2])
    round_keys[3] = swap32_neox_style(key_words[3])

    round_constants = [
        0x01000000,
        0x02000000,
        0x04000000,
        0x08000000,
        0x10000000,
        0x20000000,
        0x40000000,
        0x80FFFFFF,
        0x1B000000,
        0x36000000,
    ]

    for index, round_constant in enumerate(round_constants):
        word = round_keys[4 * index + 3]
        transformed = u32(
            (AES_SBOX_WORD_TABLE[byte3(word)] & 0x000000FF)
            ^ (AES_KEYEXP_MIXCOL_TABLE[byte0(word)] & 0x0000FF00)
            ^ (AES_KEYEXP_T0[byte1(word)] & 0x00FF0000)
            ^ ((AES_KEYEXP_ROTWORD_TABLE[byte2(word)] ^ round_constant) & 0xFF000000)
        )
        round_keys[4 * index + 4] = u32(round_keys[4 * index + 0] ^ transformed)
        round_keys[4 * index + 5] = u32(round_keys[4 * index + 1] ^ round_keys[4 * index + 4])
        round_keys[4 * index + 6] = u32(round_keys[4 * index + 2] ^ round_keys[4 * index + 5])
        round_keys[4 * index + 7] = u32(round_keys[4 * index + 3] ^ round_keys[4 * index + 6])

    return round_keys


def build_mode3_decrypt_round_keys(key16: bytes) -> list[int]:
    """构造 mode3 使用的解密方向轮密钥。"""
    round_keys = build_mode3_encrypt_round_keys(key16)
    total_rounds = round_keys[60]
    if total_rounds != 10:
        raise ValueError(f"unexpected rounds: {total_rounds}")

    for left_round in range((total_rounds + 1) // 2):
        right_round = total_rounds - left_round
        for lane in range(4):
            left_index = 4 * left_round + lane
            right_index = 4 * right_round + lane
            round_keys[left_index], round_keys[right_index] = round_keys[right_index], round_keys[left_index]

    def transform_round_word(word: int) -> int:
        return u32(
            AES_DEC_T0[AES_SBOX[byte0(word)]]
            ^ AES_DEC_T1[AES_SBOX[byte3(word)]]
            ^ AES_DEC_T2[AES_SBOX[byte2(word)]]
            ^ AES_DEC_T3[AES_SBOX[byte1(word)]]
        )

    for round_index in range(1, total_rounds):
        base = 4 * round_index
        round_keys[base + 0] = transform_round_word(round_keys[base + 0])
        round_keys[base + 1] = transform_round_word(round_keys[base + 1])
        round_keys[base + 2] = transform_round_word(round_keys[base + 2])
        round_keys[base + 3] = transform_round_word(round_keys[base + 3])

    return round_keys


def decrypt_mode3_block(block16: bytes, round_keys: list[int]) -> bytes:
    """解密单个 16 字节块。"""
    if len(block16) != 16:
        raise ValueError("block16 必须正好 16 字节")
    if len(round_keys) < 61:
        raise ValueError("round_keys 长度异常")

    x0, x1, x2, x3 = struct.unpack("<4I", block16)

    temp7 = ror32(x3, 8)
    temp8 = rol32(x2, 8)
    temp9 = rol32(x1, 8)
    state3 = u32(temp7 ^ round_keys[3] ^ ((temp7 ^ rol32(x3, 8)) & 0x00FF00FF))

    temp11 = ror32(x0, 8)
    temp12 = ror32(x2, 8)
    temp13 = ror32(x1, 8)

    state2 = u32(temp12 ^ round_keys[2] ^ ((temp12 ^ temp8) & 0x00FF00FF))
    state1 = u32(temp13 ^ round_keys[1] ^ ((temp13 ^ temp9) & 0x00FF00FF))
    state0 = u32(temp11 ^ round_keys[0] ^ ((temp11 ^ rol32(x0, 8)) & 0x00FF00FF))

    v17 = u32(round_keys[4] ^ AES_DEC_T0[byte0(state1)] ^ AES_DEC_T1[byte3(state0)] ^ AES_DEC_T2[byte2(state3)] ^ AES_DEC_T3[byte1(state2)])
    v18 = u32(round_keys[5] ^ AES_DEC_T0[byte0(state2)] ^ AES_DEC_T1[byte3(state1)] ^ AES_DEC_T3[byte1(state3)] ^ AES_DEC_T2[byte2(state0)])
    v19 = u32(round_keys[6] ^ AES_DEC_T0[byte0(state3)] ^ AES_DEC_T1[byte3(state2)] ^ AES_DEC_T3[byte1(state0)] ^ AES_DEC_T2[byte2(state1)])
    v21 = u32(round_keys[7] ^ AES_DEC_T0[byte0(state0)] ^ AES_DEC_T1[byte3(state3)] ^ AES_DEC_T2[byte2(state2)] ^ AES_DEC_T3[byte1(state1)])

    round_key_index = 8
    middle_rounds = (round_keys[60] >> 1) - 1

    while middle_rounds:
        t24 = u32(round_keys[round_key_index + 3] ^ AES_DEC_T0[byte0(v17)] ^ AES_DEC_T1[byte3(v21)] ^ AES_DEC_T2[byte2(v19)] ^ AES_DEC_T3[byte1(v18)])
        t25 = u32(round_keys[round_key_index + 2] ^ AES_DEC_T0[byte0(v21)] ^ AES_DEC_T1[byte3(v19)] ^ AES_DEC_T2[byte2(v18)] ^ AES_DEC_T3[byte1(v17)])
        t26 = u32(round_keys[round_key_index + 1] ^ AES_DEC_T0[byte0(v19)] ^ AES_DEC_T1[byte3(v18)] ^ AES_DEC_T3[byte1(v21)] ^ AES_DEC_T2[byte2(v17)])
        t27 = u32(round_keys[round_key_index + 0] ^ AES_DEC_T0[byte0(v18)] ^ AES_DEC_T1[byte3(v17)] ^ AES_DEC_T2[byte2(v21)] ^ AES_DEC_T3[byte1(v19)])

        v17 = u32(round_keys[round_key_index + 4] ^ AES_DEC_T0[byte0(t26)] ^ AES_DEC_T1[byte3(t27)] ^ AES_DEC_T2[byte2(t24)] ^ AES_DEC_T3[byte1(t25)])
        v18 = u32(round_keys[round_key_index + 5] ^ AES_DEC_T0[byte0(t25)] ^ AES_DEC_T1[byte3(t26)] ^ AES_DEC_T3[byte1(t24)] ^ AES_DEC_T2[byte2(t27)])
        v19 = u32(round_keys[round_key_index + 6] ^ AES_DEC_T0[byte0(t24)] ^ AES_DEC_T1[byte3(t25)] ^ AES_DEC_T2[byte2(t26)] ^ AES_DEC_T3[byte1(t27)])
        v21 = u32(round_keys[round_key_index + 7] ^ AES_DEC_T0[byte0(t27)] ^ AES_DEC_T1[byte3(t24)] ^ AES_DEC_T2[byte2(t25)] ^ AES_DEC_T3[byte1(t26)])

        round_key_index += 8
        middle_rounds -= 1

    y0 = u32(
        round_keys[round_key_index + 0]
        ^ AES_INV_SBOX[byte0(v18)]
        ^ ((AES_INV_SBOX[byte1(v19)] ^ (((AES_INV_SBOX[byte3(v17)] << 8) ^ AES_INV_SBOX[byte2(v21)]) << 8)) << 8)
    )
    y1 = u32(
        round_keys[round_key_index + 1]
        ^ AES_INV_SBOX[byte0(v19)]
        ^ ((AES_INV_SBOX[byte1(v21)] ^ ((AES_INV_SBOX[byte2(v17)] ^ (AES_INV_SBOX[byte3(v18)] << 8)) << 8)) << 8)
    )
    y2 = u32(
        round_keys[round_key_index + 2]
        ^ AES_INV_SBOX[byte0(v21)]
        ^ ((AES_INV_SBOX[byte1(v17)] ^ (((AES_INV_SBOX[byte3(v19)] << 8) ^ AES_INV_SBOX[byte2(v18)]) << 8)) << 8)
    )
    y3 = u32(
        round_keys[round_key_index + 3]
        ^ AES_INV_SBOX[byte0(v17)]
        ^ ((AES_INV_SBOX[byte1(v18)] ^ (((AES_INV_SBOX[byte3(v21)] << 8) ^ AES_INV_SBOX[byte2(v19)]) << 8)) << 8)
    )

    out0 = swap32_neox_style(y0)
    out1 = swap32_neox_style(y1)
    out2 = swap32_neox_style(y2)
    out3 = swap32_neox_style(y3)

    return struct.pack("<4I", out0, out1, out2, out3)


def decrypt_mode3_buffer(data: bytes | bytearray, key16: bytes = EGGPARTY_MODE3_INDEX_KEY) -> bytes:
    """按 16 字节块批量解密，尾部不足 16 字节部分保持原样。"""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data 必须是 bytes 或 bytearray")
    if len(key16) != 16:
        raise ValueError("key16 必须正好 16 字节")

    round_keys = build_mode3_decrypt_round_keys(key16)

    buffer = bytearray(data)
    block_count = len(buffer) >> 4
    for block_index in range(block_count):
        offset = block_index * 16
        buffer[offset:offset + 16] = decrypt_mode3_block(bytes(buffer[offset:offset + 16]), round_keys)

    return bytes(buffer)


def decrypt_eggparty_index(index_data: bytes | bytearray, key16: bytes = EGGPARTY_MODE3_INDEX_KEY) -> bytes:
    """EggParty NPK 索引解密入口。"""
    return decrypt_mode3_buffer(index_data, key16)


__all__ = [
    "EGGPARTY_MODE3_INDEX_KEY",
    "build_mode3_encrypt_round_keys",
    "build_mode3_decrypt_round_keys",
    "decrypt_mode3_block",
    "decrypt_mode3_buffer",
    "decrypt_eggparty_index",
]
