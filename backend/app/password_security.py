"""Modern salted password KDF and constant-time verification; no external dependencies."""
import hashlib,secrets,hmac,re
N=32768;R=8;P=1
WEAK={'password','password123','password123456','123456789012','qwerty123456','admin12345678','letmein123456','changeme123456'}
def validate_password(value,email=''):
 if not isinstance(value,str) or not 12<=len(value)<=128 or value.casefold() in WEAK or re.fullmatch(r'(?:password|welcome|administrator|admin|qwerty|letmein|changeme|пароль)[0-9]*',re.sub(r'[^a-zа-я0-9]','',value.casefold())) or len(set(value))<5 or (email and len(email.split('@')[0])>=4 and email.split('@')[0].casefold() in value.casefold()):raise ValueError('weak_password')
def hash_password(value):
 salt=secrets.token_bytes(16);digest=hashlib.scrypt(value.encode(),salt=salt,n=N,r=R,p=P,maxmem=64*1024*1024,dklen=64)
 return 'scrypt$32768$8$1$'+salt.hex()+'$'+digest.hex()
def verify_password(value,encoded):
 try:
  algorithm,n,r,p,salt,digest=encoded.split('$')
  if (algorithm,n,r,p)!=('scrypt','32768','8','1') or len(salt)!=32 or len(digest)!=128:return False
  actual=hashlib.scrypt(value.encode(),salt=bytes.fromhex(salt),n=N,r=R,p=P,maxmem=64*1024*1024,dklen=64)
  return hmac.compare_digest(actual,bytes.fromhex(digest))
 except (ValueError,TypeError,AttributeError):return False
