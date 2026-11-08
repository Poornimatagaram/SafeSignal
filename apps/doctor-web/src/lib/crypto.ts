// X25519 key pairs and libsodium sealed boxes (contract 2.0).
// Base64 is the STANDARD alphabet with padding, to match Python's base64 / PyNaCl;
// libsodium-wrappers defaults to URL-safe without padding, so the variant is always explicit.
import sodium from 'libsodium-wrappers'

export interface KeyPair {
  publicKey: string // base64
  privateKey: string // base64; never leaves IndexedDB
}

const B64 = () => sodium.base64_variants.ORIGINAL
const from64 = (s: string) => sodium.from_base64(s, B64())
const to64 = (b: Uint8Array) => sodium.to_base64(b, B64())

export async function generateKeyPair(): Promise<KeyPair> {
  await sodium.ready
  const kp = sodium.crypto_box_keypair()
  return { publicKey: to64(kp.publicKey), privateKey: to64(kp.privateKey) }
}

export async function openSealed(ciphertextB64: string, kp: KeyPair): Promise<Uint8Array> {
  await sodium.ready
  return sodium.crypto_box_seal_open(from64(ciphertextB64), from64(kp.publicKey), from64(kp.privateKey))
}

export async function openSealedText(ciphertextB64: string, kp: KeyPair): Promise<string> {
  return sodium.to_string(await openSealed(ciphertextB64, kp))
}

// Key grant (D-064): the wrapped key is a sealed box of the org's raw 32-byte private key,
// sealed to the member's personal public key.
export async function wrapOrgKey(orgPrivateKeyB64: string, memberPublicKeyB64: string): Promise<string> {
  await sodium.ready
  return to64(sodium.crypto_box_seal(from64(orgPrivateKeyB64), from64(memberPublicKeyB64)))
}

export async function unwrapOrgKey(wrappedB64: string, personal: KeyPair): Promise<KeyPair> {
  const priv = await openSealed(wrappedB64, personal)
  if (priv.length !== 32) throw new Error('key grant does not hold a 32-byte key')
  return { publicKey: to64(sodium.crypto_scalarmult_base(priv)), privateKey: to64(priv) }
}

export async function isPublicKey(b64: string): Promise<boolean> {
  await sodium.ready
  try {
    return from64(b64.trim()).length === 32
  } catch {
    return false
  }
}
