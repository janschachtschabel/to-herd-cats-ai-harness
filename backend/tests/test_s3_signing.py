"""AWS Signature Version 4 (plan M9 decision 18): the signer reproduces the examples
AWS publishes, as fixed values: the four of the S3 documentation ("Signature
Calculations for the Authorization Header: Transferring Payload in a Single Chunk",
bucket `examplebucket`, 24 May 2013) and `get-vanilla` of the general SigV4 test
suite."""

from datetime import UTC, datetime

import pytest

from app.core.s3_signing import Credentials, canonical_request, sign

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
S3_DOCS = Credentials("AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
S3_AT = datetime(2013, 5, 24, tzinfo=UTC)
S3_HOST = "examplebucket.s3.amazonaws.com"
CREDENTIAL = "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request"


def _s3(**headers: str) -> dict[str, str]:
    return {"x-amz-date": "20130524T000000Z", **headers}


S3_EXAMPLES = [
    pytest.param(
        "GET",
        "/test.txt",
        [],
        _s3(range="bytes=0-9", **{"x-amz-content-sha256": EMPTY}),
        EMPTY,
        "host;range;x-amz-content-sha256;x-amz-date",
        "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41",
        id="get-object",
    ),
    pytest.param(
        "PUT",
        "/test$file.text",
        [],
        _s3(
            date="Fri, 24 May 2013 00:00:00 GMT",
            **{
                "x-amz-storage-class": "REDUCED_REDUNDANCY",
                "x-amz-content-sha256": (
                    "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
                ),
            },
        ),
        "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072",
        "date;host;x-amz-content-sha256;x-amz-date;x-amz-storage-class",
        "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd",
        id="put-object",
    ),
    pytest.param(
        "GET",
        "/",
        [("lifecycle", "")],
        _s3(**{"x-amz-content-sha256": EMPTY}),
        EMPTY,
        "host;x-amz-content-sha256;x-amz-date",
        "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543",
        id="get-bucket-lifecycle",
    ),
    pytest.param(
        "GET",
        "/",
        [("max-keys", "2"), ("prefix", "J")],
        _s3(**{"x-amz-content-sha256": EMPTY}),
        EMPTY,
        "host;x-amz-content-sha256;x-amz-date",
        "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7",
        id="list-objects",
    ),
]


@pytest.mark.parametrize(
    ("method", "path", "query", "headers", "payload", "signed", "signature"), S3_EXAMPLES
)
def test_sigv4_matches_the_aws_examples(
    method: str,
    path: str,
    query: list[tuple[str, str]],
    headers: dict[str, str],
    payload: str,
    signed: str,
    signature: str,
) -> None:
    authorization = sign(
        method=method,
        host=S3_HOST,
        path=path,
        query=query,
        headers=headers,
        payload_sha256=payload,
        credentials=S3_DOCS,
        region="us-east-1",
        at=S3_AT,
    )
    assert authorization == (
        f"AWS4-HMAC-SHA256 {CREDENTIAL},SignedHeaders={signed},Signature={signature}"
    )


def test_sigv4_matches_the_get_vanilla_case_of_the_test_suite() -> None:
    authorization = sign(
        method="GET",
        host="example.amazonaws.com",
        path="/",
        query=[],
        headers={"X-Amz-Date": "20150830T123600Z"},
        payload_sha256=EMPTY,
        credentials=Credentials("AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"),
        region="us-east-1",
        service="service",
        at=datetime(2015, 8, 30, 12, 36, tzinfo=UTC),
    )
    assert authorization == (
        "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request,"
        " SignedHeaders=host;x-amz-date,"
        " Signature=5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"
    ).replace(", ", ",")


def test_the_canonical_request_of_the_get_object_example() -> None:
    request, signed = canonical_request(
        method="GET",
        host=S3_HOST,
        path="/test.txt",
        query=[],
        headers=_s3(range="bytes=0-9", **{"x-amz-content-sha256": EMPTY}),
        payload_sha256=EMPTY,
    )
    assert signed == "host;range;x-amz-content-sha256;x-amz-date"
    assert request == "\n".join(
        [
            "GET",
            "/test.txt",
            "",
            f"host:{S3_HOST}",
            "range:bytes=0-9",
            f"x-amz-content-sha256:{EMPTY}",
            "x-amz-date:20130524T000000Z",
            "",
            signed,
            EMPTY,
        ]
    )


def test_keys_and_query_values_are_encoded_once() -> None:
    request, _ = canonical_request(
        method="GET",
        host="s3.local",
        path="/bucket/a b/ä+~",
        query=[("prefix", "a/b c"), ("continuation-token", "x=y+z")],
        headers={},
        payload_sha256=EMPTY,
    )
    lines = request.split("\n")
    assert lines[1] == "/bucket/a%20b/%C3%A4%2B~"
    assert lines[2] == "continuation-token=x%3Dy%2Bz&prefix=a%2Fb%20c"


def test_credentials_never_show_the_secret() -> None:
    credentials = Credentials("AKIDEXAMPLE", "very-secret-key")
    assert "very-secret-key" not in repr(credentials)
    assert "very-secret-key" not in str(credentials)
