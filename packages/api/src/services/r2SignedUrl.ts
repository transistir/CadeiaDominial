const encoder = new TextEncoder();

const toHex = (buffer: ArrayBuffer) =>
  Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");

const hash = async (value: string) => {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return toHex(digest);
};

const toArrayBuffer = (value: ArrayBuffer | Uint8Array) => {
  if (value instanceof Uint8Array) {
    const copy = new Uint8Array(value.byteLength);
    copy.set(value);
    return copy.buffer;
  }
  return value.slice(0);
};

const hmac = async (key: ArrayBuffer | Uint8Array, value: string) => {
  const keyBuffer = toArrayBuffer(key);
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBuffer,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", cryptoKey, encoder.encode(value));
  return signature;
};

const encodeRfc3986 = (value: string) =>
  encodeURIComponent(value).replace(/[!'()*]/g, (char) =>
    `%${char.charCodeAt(0).toString(16).toUpperCase()}`
  );

const encodePath = (value: string) =>
  value
    .split("/")
    .map((segment) => encodeRfc3986(segment))
    .join("/");

const formatAmzDate = (date: Date) => {
  const pad = (value: number) => String(value).padStart(2, "0");
  const year = date.getUTCFullYear();
  const month = pad(date.getUTCMonth() + 1);
  const day = pad(date.getUTCDate());
  const hours = pad(date.getUTCHours());
  const minutes = pad(date.getUTCMinutes());
  const seconds = pad(date.getUTCSeconds());

  return {
    amzDate: `${year}${month}${day}T${hours}${minutes}${seconds}Z`,
    dateStamp: `${year}${month}${day}`
  };
};

const getSigningKey = async (
  secretAccessKey: string,
  dateStamp: string,
  region: string,
  service: string
) => {
  const kDate = await hmac(encoder.encode(`AWS4${secretAccessKey}`), dateStamp);
  const kRegion = await hmac(kDate, region);
  const kService = await hmac(kRegion, service);
  return hmac(kService, "aws4_request");
};

type SignedUrlOptions = {
  method: "GET" | "PUT";
  host: string;
  bucket: string;
  key: string;
  accessKeyId: string;
  secretAccessKey: string;
  expiresIn: number;
  contentType?: string;
};

export const createSignedUrl = async ({
  method,
  host,
  bucket,
  key,
  accessKeyId,
  secretAccessKey,
  expiresIn,
  contentType
}: SignedUrlOptions) => {
  const now = new Date();
  const { amzDate, dateStamp } = formatAmzDate(now);
  const region = "auto";
  const service = "s3";
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;

  const headers: Record<string, string> = { host };
  if (contentType) {
    headers["content-type"] = contentType;
  }

  const signedHeaders = Object.keys(headers)
    .map((header) => header.toLowerCase())
    .sort();
  const canonicalHeaders = signedHeaders
    .map((header) => `${header}:${headers[header]}`)
    .join("\n");

  const queryParams: Record<string, string> = {
    "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
    "X-Amz-Credential": `${accessKeyId}/${credentialScope}`,
    "X-Amz-Date": amzDate,
    "X-Amz-Expires": String(expiresIn),
    "X-Amz-SignedHeaders": signedHeaders.join(";")
  };

  const canonicalQuery = Object.entries(queryParams)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([keyName, value]) => `${encodeRfc3986(keyName)}=${encodeRfc3986(value)}`)
    .join("&");

  const canonicalUri = `/${encodePath(`${bucket}/${key}`)}`;
  const payloadHash = "UNSIGNED-PAYLOAD";

  const canonicalRequest = [
    method,
    canonicalUri,
    canonicalQuery,
    `${canonicalHeaders}\n`,
    signedHeaders.join(";"),
    payloadHash
  ].join("\n");

  const stringToSign = [
    "AWS4-HMAC-SHA256",
    amzDate,
    credentialScope,
    await hash(canonicalRequest)
  ].join("\n");

  const signingKey = await getSigningKey(secretAccessKey, dateStamp, region, service);
  const signature = toHex(await hmac(signingKey, stringToSign));

  const url = new URL(`https://${host}${canonicalUri}`);
  url.search = `${canonicalQuery}&X-Amz-Signature=${signature}`;

  return {
    url: url.toString(),
    expiresAt: new Date(now.getTime() + expiresIn * 1000).toISOString(),
    requiredHeaders: contentType ? { "Content-Type": contentType } : undefined
  };
};
