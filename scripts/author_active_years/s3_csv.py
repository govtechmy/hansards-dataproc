"""Conditional CSV writes, including support for older botocore S3 models."""


def put_csv(s3, bucket, key, frame, etag):
    def require_version(params, **kwargs):
        params['headers']['If-Match'] = etag

    event = 'before-call.s3.PutObject'
    s3.meta.events.register(event, require_version)
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=frame.to_csv(index=False).encode('utf-8'), ContentType='text/csv')
    finally:
        s3.meta.events.unregister(event, require_version)
