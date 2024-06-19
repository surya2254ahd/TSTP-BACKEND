import logging
import os

import boto3


class AwsStorageClient:
    def __init__(self, logger=None):
        self.set_logger(logger)
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY")
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_KEY")
        self.aws_bucket = os.environ.get("AWS_BUCKET_NAME")
        self.aws_bucket_region = os.environ.get("AWS_REGION")

        self.session = boto3.session.Session()

        self.s3_client = self.session.client('s3', aws_access_key_id=self.aws_access_key_id,
                                             aws_secret_access_key=self.aws_secret_access_key,
                                             region_name=self.aws_bucket_region)

    def upload_file_from_fs(self, source, filename, full_path_to_file, content_type):
        object_key = os.path.join(source, filename)

        client = self.session.resource('s3', aws_access_key_id=self.aws_access_key_id,
                                       aws_secret_access_key=self.aws_secret_access_key,
                                       region_name=self.aws_bucket_region)

        _bucket = client.Bucket(self.aws_bucket)
        _bucket.upload_file(full_path_to_file, object_key, ExtraArgs={'ContentType': content_type})

    def get_url(self, source, filename):
        object_key = os.path.join(source, filename)
        expiration_time = min(604800, int(os.environ.get('AWS_PRESIGNED_URL_EXPIRY', "1800")))

        url = self.s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': self.aws_bucket,
                'Key': object_key
            },
            ExpiresIn=expiration_time
        )

        return url

    def delete_file(self, source, filename):
        self.get_logger().info(f'S3 Storage: deleting file: {filename} for source: {source}')
        client = self.session.resource('s3', aws_access_key_id=self.aws_access_key_id,
                                       aws_secret_access_key=self.aws_secret_access_key,
                                       region_name=self.aws_bucket_region)
        object_key = os.path.join(source, filename)
        self.get_logger().debug(f'S3 Storage: deleting object: {object_key} from bucket: {self.aws_bucket}')
        client.Object(self.aws_bucket, object_key).delete()

    def get_logger(self):
        return self.logger

    def set_logger(self, logger=None):
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
