type ReadableStreamLike = ReadableStream<Uint8Array> | ArrayBuffer;

type R2Object = {
  body: ReadableStreamLike | null;
  etag: string;
  size: number;
  httpMetadata?: {
    contentType?: string;
  };
};

type R2Bucket = {
  get: (key: string) => Promise<R2Object | null>;
  put: (
    key: string,
    value: ArrayBuffer | ReadableStreamLike,
    options?: { httpMetadata?: { contentType?: string } }
  ) => Promise<unknown>;
};

type FileLike = {
  arrayBuffer: () => Promise<ArrayBuffer>;
  type?: string;
  name?: string;
  size?: number;
};

type PutFileResult = {
  key: string;
  size: number;
  contentType: string | null;
};

export const putFileIntoBucket = async (bucket: R2Bucket, key: string, file: FileLike) => {
  const buffer = await file.arrayBuffer();
  const contentType = file.type ?? null;

  await bucket.put(key, buffer, {
    httpMetadata: contentType ? { contentType } : undefined
  });

  return {
    key,
    size: file.size ?? buffer.byteLength,
    contentType
  } satisfies PutFileResult;
};

export const getFileFromBucket = async (bucket: R2Bucket, key: string) => {
  return bucket.get(key);
};
