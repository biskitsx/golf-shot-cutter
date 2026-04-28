import boto3
import pytest
from moto import mock_aws

from golf_infrastructure.r2.storage_gateway import R2StorageGateway


@pytest.fixture
def s3_setup():
    with mock_aws():
        client = boto3.client(
            "s3",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            region_name="us-east-1",
        )
        client.create_bucket(Bucket="golf-test")
        yield client


async def test_signed_put_url_contains_key_and_expiry(s3_setup):
    gw = R2StorageGateway(
        endpoint=None,  # use default for moto
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    out = await gw.signed_put_url("raw/ses_1/v.mp4", content_type="video/mp4")
    assert "raw/ses_1/v.mp4" in out.url
    assert out.expires_at is not None


async def test_signed_get_url_returns_signed(s3_setup):
    gw = R2StorageGateway(
        endpoint=None,
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    out = await gw.signed_get_url("clips/ses_1/shot_001.mp4")
    assert "clips/ses_1/shot_001.mp4" in out.url


async def test_delete_object_removes_from_bucket(s3_setup):
    s3_setup.put_object(Bucket="golf-test", Key="clips/x.mp4", Body=b"hello")
    gw = R2StorageGateway(
        endpoint=None,
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    await gw.delete_object("clips/x.mp4")
    resp = s3_setup.list_objects_v2(Bucket="golf-test")
    assert resp.get("KeyCount", 0) == 0
