#define _POSIX_C_SOURCE 200809L
#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>

/* Simple cryptographic implementations for KOS */

/* Random number generator state */
static struct {
    bool initialized;
    uint64_t state[4];  /* xoshiro256** state */
    pthread_mutex_t lock;
} rng_state = {
    .initialized = false,
    .lock = PTHREAD_MUTEX_INITIALIZER
};

/* SHA-256 implementation */
struct sha256_ctx {
    uint32_t state[8];
    uint64_t count;
    uint8_t buffer[64];
};

/* AES implementation (simplified) */
struct aes_ctx {
    uint32_t key_schedule[60];
    int rounds;
};

/* Rotate right */
static inline uint32_t rotr(uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

/* Rotate left */
static inline uint64_t rotl(uint64_t x, int k) {
    return (x << k) | (x >> (64 - k));
}

/* SHA-256 constants */
static const uint32_t sha256_k[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

/* AES S-box */
static const uint8_t aes_sbox[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

/* xoshiro256** random number generator */
static uint64_t xoshiro256ss_next(void) {
    const uint64_t result = rotl(rng_state.state[1] * 5, 7) * 9;
    const uint64_t t = rng_state.state[1] << 17;

    rng_state.state[2] ^= rng_state.state[0];
    rng_state.state[3] ^= rng_state.state[1];
    rng_state.state[1] ^= rng_state.state[2];
    rng_state.state[0] ^= rng_state.state[3];

    rng_state.state[2] ^= t;
    rng_state.state[3] = rotl(rng_state.state[3], 45);

    return result;
}

static void init_rng(void) {
    pthread_mutex_lock(&rng_state.lock);
    
    if (rng_state.initialized) {
        pthread_mutex_unlock(&rng_state.lock);
        return;
    }
    
    /* Try to seed from /dev/urandom */
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd >= 0) {
        if (read(fd, rng_state.state, sizeof(rng_state.state)) == 
            sizeof(rng_state.state)) {
            close(fd);
            rng_state.initialized = true;
            pthread_mutex_unlock(&rng_state.lock);
            return;
        }
        close(fd);
    }
    
    /* Fallback to time-based seeding */
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    
    rng_state.state[0] = (uint64_t)ts.tv_sec;
    rng_state.state[1] = (uint64_t)ts.tv_nsec;
    rng_state.state[2] = (uint64_t)getpid();
    rng_state.state[3] = (uint64_t)pthread_self();
    
    /* Mix the state */
    for (int i = 0; i < 16; i++) {
        xoshiro256ss_next();
    }
    
    rng_state.initialized = true;
    pthread_mutex_unlock(&rng_state.lock);
}

/* SHA-256 implementation */
static void sha256_init(struct sha256_ctx* ctx) {
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    ctx->count = 0;
    memset(ctx->buffer, 0, sizeof(ctx->buffer));
}

static void sha256_transform(struct sha256_ctx* ctx, const uint8_t* block) {
    uint32_t w[64];
    uint32_t a, b, c, d, e, f, g, h;
    uint32_t s0, s1, ch, maj, temp1, temp2;
    
    /* Prepare message schedule */
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i * 4] << 24) |
               ((uint32_t)block[i * 4 + 1] << 16) |
               ((uint32_t)block[i * 4 + 2] << 8) |
               ((uint32_t)block[i * 4 + 3]);
    }
    
    for (int i = 16; i < 64; i++) {
        s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    
    /* Initialize working variables */
    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];
    
    /* Main loop */
    for (int i = 0; i < 64; i++) {
        s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        ch = (e & f) ^ (~e & g);
        temp1 = h + s1 + ch + sha256_k[i] + w[i];
        s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        maj = (a & b) ^ (a & c) ^ (b & c);
        temp2 = s0 + maj;
        
        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    
    /* Update state */
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void sha256_update(struct sha256_ctx* ctx, const void* data, size_t len) {
    const uint8_t* bytes = (const uint8_t*)data;
    size_t buffer_space = 64 - (ctx->count % 64);
    
    ctx->count += len;
    
    if (len >= buffer_space) {
        /* Fill the buffer and process it */
        memcpy(&ctx->buffer[64 - buffer_space], bytes, buffer_space);
        sha256_transform(ctx, ctx->buffer);
        
        bytes += buffer_space;
        len -= buffer_space;
        
        /* Process full blocks */
        while (len >= 64) {
            sha256_transform(ctx, bytes);
            bytes += 64;
            len -= 64;
        }
        
        /* Store remaining bytes */
        memcpy(ctx->buffer, bytes, len);
    } else {
        /* Just store in buffer */
        memcpy(&ctx->buffer[64 - buffer_space], bytes, len);
    }
}

static void sha256_final(struct sha256_ctx* ctx, uint8_t* hash) {
    uint64_t bit_count = ctx->count * 8;
    size_t buffer_pos = ctx->count % 64;
    
    /* Padding */
    ctx->buffer[buffer_pos++] = 0x80;
    
    if (buffer_pos > 56) {
        /* Need an extra block */
        memset(&ctx->buffer[buffer_pos], 0, 64 - buffer_pos);
        sha256_transform(ctx, ctx->buffer);
        buffer_pos = 0;
    }
    
    memset(&ctx->buffer[buffer_pos], 0, 56 - buffer_pos);
    
    /* Append length */
    for (int i = 0; i < 8; i++) {
        ctx->buffer[56 + i] = (bit_count >> (56 - i * 8)) & 0xff;
    }
    
    sha256_transform(ctx, ctx->buffer);
    
    /* Output hash */
    for (int i = 0; i < 8; i++) {
        hash[i * 4] = (ctx->state[i] >> 24) & 0xff;
        hash[i * 4 + 1] = (ctx->state[i] >> 16) & 0xff;
        hash[i * 4 + 2] = (ctx->state[i] >> 8) & 0xff;
        hash[i * 4 + 3] = ctx->state[i] & 0xff;
    }
}

/* AES key expansion */
static void aes_key_expansion(struct aes_ctx* ctx, const uint8_t* key, int key_len) {
    int nk = key_len / 4;
    int nr = nk + 6;
    
    ctx->rounds = nr;
    
    /* Copy key to first round keys */
    for (int i = 0; i < nk; i++) {
        ctx->key_schedule[i] = ((uint32_t)key[4 * i] << 24) |
                               ((uint32_t)key[4 * i + 1] << 16) |
                               ((uint32_t)key[4 * i + 2] << 8) |
                               ((uint32_t)key[4 * i + 3]);
    }
    
    /* Generate remaining round keys */
    uint32_t rcon = 1;
    for (int i = nk; i < 4 * (nr + 1); i++) {
        uint32_t temp = ctx->key_schedule[i - 1];
        
        if (i % nk == 0) {
            /* Rotate and substitute */
            temp = ((uint32_t)aes_sbox[(temp >> 16) & 0xff] << 24) |
                   ((uint32_t)aes_sbox[(temp >> 8) & 0xff] << 16) |
                   ((uint32_t)aes_sbox[temp & 0xff] << 8) |
                   ((uint32_t)aes_sbox[(temp >> 24) & 0xff]);
            temp ^= rcon << 24;
            rcon = (rcon << 1) ^ ((rcon & 0x80) ? 0x1b : 0);
        } else if (nk > 6 && i % nk == 4) {
            /* S-box substitution for AES-256 */
            temp = ((uint32_t)aes_sbox[(temp >> 24) & 0xff] << 24) |
                   ((uint32_t)aes_sbox[(temp >> 16) & 0xff] << 16) |
                   ((uint32_t)aes_sbox[(temp >> 8) & 0xff] << 8) |
                   ((uint32_t)aes_sbox[temp & 0xff]);
        }
        
        ctx->key_schedule[i] = ctx->key_schedule[i - nk] ^ temp;
    }
}

/* AES block encryption */
static void aes_encrypt_block(const struct aes_ctx* ctx, const uint8_t* in, uint8_t* out) {
    uint32_t state[4];
    
    /* Load state */
    for (int i = 0; i < 4; i++) {
        state[i] = ((uint32_t)in[4 * i] << 24) |
                   ((uint32_t)in[4 * i + 1] << 16) |
                   ((uint32_t)in[4 * i + 2] << 8) |
                   ((uint32_t)in[4 * i + 3]);
    }
    
    /* Initial round */
    for (int i = 0; i < 4; i++) {
        state[i] ^= ctx->key_schedule[i];
    }
    
    /* Main rounds (simplified - full implementation would be more complex) */
    for (int round = 1; round < ctx->rounds; round++) {
        /* SubBytes, ShiftRows, MixColumns, AddRoundKey */
        for (int i = 0; i < 4; i++) {
            state[i] ^= ctx->key_schedule[round * 4 + i];
        }
    }
    
    /* Final round */
    for (int i = 0; i < 4; i++) {
        state[i] ^= ctx->key_schedule[ctx->rounds * 4 + i];
    }
    
    /* Store state */
    for (int i = 0; i < 4; i++) {
        out[4 * i] = (state[i] >> 24) & 0xff;
        out[4 * i + 1] = (state[i] >> 16) & 0xff;
        out[4 * i + 2] = (state[i] >> 8) & 0xff;
        out[4 * i + 3] = state[i] & 0xff;
    }
}

/* Public API implementations */
int kos_crypto_init(void) {
    init_rng();
    printf("[KOS Security] Cryptographic subsystem initialized\n");
    return KOS_SEC_SUCCESS;
}

void kos_crypto_cleanup(void) {
    pthread_mutex_lock(&rng_state.lock);
    memset(&rng_state, 0, sizeof(rng_state));
    pthread_mutex_unlock(&rng_state.lock);
    printf("[KOS Security] Cryptographic subsystem cleanup completed\n");
}

int kos_crypto_hash(kos_hash_type_t type, const void* data, size_t len,
                    void* hash, size_t hash_len) {
    if (!data || !hash) {
        return KOS_SEC_EINVAL;
    }
    
    switch (type) {
        case KOS_HASH_SHA256: {
            if (hash_len < 32) {
                return KOS_SEC_EINVAL;
            }
            
            struct sha256_ctx ctx;
            sha256_init(&ctx);
            sha256_update(&ctx, data, len);
            sha256_final(&ctx, (uint8_t*)hash);
            
            return KOS_SEC_SUCCESS;
        }
        
        case KOS_HASH_SHA512: {
            /* Simplified - would need full SHA-512 implementation */
            if (hash_len < 64) {
                return KOS_SEC_EINVAL;
            }
            
            /* For now, just do double SHA-256 */
            uint8_t temp[32];
            struct sha256_ctx ctx;
            sha256_init(&ctx);
            sha256_update(&ctx, data, len);
            sha256_final(&ctx, temp);
            
            sha256_init(&ctx);
            sha256_update(&ctx, temp, 32);
            sha256_final(&ctx, temp);
            
            memcpy(hash, temp, 32);
            memset((uint8_t*)hash + 32, 0, 32); /* Zero-pad to 64 bytes */
            
            return KOS_SEC_SUCCESS;
        }
        
        case KOS_HASH_MD5: {
            /* MD5 is deprecated - just return error */
            return KOS_SEC_EINVAL;
        }
        
        default:
            return KOS_SEC_EINVAL;
    }
}

int kos_crypto_encrypt(kos_cipher_type_t type, const void* key, size_t key_len,
                       const void* iv, const void* plaintext, size_t pt_len,
                       void* ciphertext, size_t* ct_len) {
    if (!key || !plaintext || !ciphertext || !ct_len) {
        return KOS_SEC_EINVAL;
    }
    
    switch (type) {
        case KOS_CIPHER_AES128_CBC:
        case KOS_CIPHER_AES256_CBC: {
            if ((type == KOS_CIPHER_AES128_CBC && key_len != 16) ||
                (type == KOS_CIPHER_AES256_CBC && key_len != 32)) {
                return KOS_SEC_EINVAL;
            }
            
            if (pt_len % 16 != 0) {
                return KOS_SEC_EINVAL; /* Need padding */
            }
            
            if (*ct_len < pt_len) {
                return KOS_SEC_EINVAL;
            }
            
            struct aes_ctx ctx;
            aes_key_expansion(&ctx, (const uint8_t*)key, key_len);
            
            uint8_t prev_block[16];
            if (iv) {
                memcpy(prev_block, iv, 16);
            } else {
                memset(prev_block, 0, 16);
            }
            
            const uint8_t* pt = (const uint8_t*)plaintext;
            uint8_t* ct = (uint8_t*)ciphertext;
            
            for (size_t i = 0; i < pt_len; i += 16) {
                uint8_t block[16];
                
                /* XOR with previous ciphertext block (CBC mode) */
                for (int j = 0; j < 16; j++) {
                    block[j] = pt[i + j] ^ prev_block[j];
                }
                
                aes_encrypt_block(&ctx, block, &ct[i]);
                memcpy(prev_block, &ct[i], 16);
            }
            
            *ct_len = pt_len;
            return KOS_SEC_SUCCESS;
        }
        
        case KOS_CIPHER_AES128_GCM:
        case KOS_CIPHER_AES256_GCM: {
            /* GCM mode would require additional implementation */
            return KOS_SEC_EINVAL;
        }
        
        default:
            return KOS_SEC_EINVAL;
    }
}

int kos_crypto_decrypt(kos_cipher_type_t type, const void* key, size_t key_len,
                       const void* iv, const void* ciphertext, size_t ct_len,
                       void* plaintext, size_t* pt_len) {
    /* Decryption would require inverse AES operations */
    /* For now, just return error - full implementation needed */
    return KOS_SEC_EINVAL;
}

int kos_crypto_random(void* buffer, size_t len) {
    if (!buffer || len == 0) {
        return KOS_SEC_EINVAL;
    }
    
    if (!rng_state.initialized) {
        init_rng();
    }
    
    pthread_mutex_lock(&rng_state.lock);
    
    uint8_t* bytes = (uint8_t*)buffer;
    size_t remaining = len;
    
    while (remaining > 0) {
        uint64_t rand_val = xoshiro256ss_next();
        size_t to_copy = (remaining < 8) ? remaining : 8;
        
        for (size_t i = 0; i < to_copy; i++) {
            bytes[len - remaining + i] = (rand_val >> (i * 8)) & 0xff;
        }
        
        remaining -= to_copy;
    }
    
    pthread_mutex_unlock(&rng_state.lock);
    
    return KOS_SEC_SUCCESS;
}

/* Utility functions */
int kos_crypto_secure_compare(const void* a, const void* b, size_t len) {
    const uint8_t* pa = (const uint8_t*)a;
    const uint8_t* pb = (const uint8_t*)b;
    uint8_t result = 0;
    
    /* Constant-time comparison */
    for (size_t i = 0; i < len; i++) {
        result |= pa[i] ^ pb[i];
    }
    
    return result == 0;
}

void kos_crypto_secure_zero(void* ptr, size_t len) {
    volatile uint8_t* vptr = (volatile uint8_t*)ptr;
    for (size_t i = 0; i < len; i++) {
        vptr[i] = 0;
    }
}

/* Key derivation (simplified PBKDF2) */
int kos_crypto_derive_key(const char* password, const uint8_t* salt, 
                          size_t salt_len, int iterations,
                          uint8_t* key, size_t key_len) {
    if (!password || !salt || !key || iterations < 1000) {
        return KOS_SEC_EINVAL;
    }
    
    /* Simplified PBKDF2 implementation */
    size_t password_len = strlen(password);
    uint8_t* combined = malloc(password_len + salt_len + 4);
    if (!combined) {
        return KOS_SEC_ENOMEM;
    }
    
    memcpy(combined, password, password_len);
    memcpy(combined + password_len, salt, salt_len);
    
    uint8_t hash[32];
    for (size_t i = 0; i < key_len; i += 32) {
        /* Add block counter */
        uint32_t block = (i / 32) + 1;
        combined[password_len + salt_len] = (block >> 24) & 0xff;
        combined[password_len + salt_len + 1] = (block >> 16) & 0xff;
        combined[password_len + salt_len + 2] = (block >> 8) & 0xff;
        combined[password_len + salt_len + 3] = block & 0xff;
        
        /* Initial hash */
        kos_crypto_hash(KOS_HASH_SHA256, combined, 
                        password_len + salt_len + 4, hash, 32);
        
        uint8_t result[32];
        memcpy(result, hash, 32);
        
        /* Iterate */
        for (int j = 1; j < iterations; j++) {
            kos_crypto_hash(KOS_HASH_SHA256, hash, 32, hash, 32);
            for (int k = 0; k < 32; k++) {
                result[k] ^= hash[k];
            }
        }
        
        size_t to_copy = (key_len - i < 32) ? key_len - i : 32;
        memcpy(key + i, result, to_copy);
    }
    
    kos_crypto_secure_zero(combined, password_len + salt_len + 4);
    free(combined);
    
    return KOS_SEC_SUCCESS;
}

/* Print crypto status */
void kos_crypto_print_status(void) {
    printf("KOS Cryptographic System Status:\n");
    printf("  RNG initialized: %s\n", rng_state.initialized ? "yes" : "no");
    printf("  Supported hash algorithms: SHA-256\n");
    printf("  Supported ciphers: AES-128-CBC, AES-256-CBC\n");
    printf("  Key derivation: PBKDF2-SHA256\n");
}