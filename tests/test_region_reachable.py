"""region_reachable: connect failure -> skip; endpoint answers (even an error) -> keep."""

from botocore.exceptions import ClientError, EndpointConnectionError

from pump_aws_radar import inventory


class _Session:
    def __init__(self, ec2):
        self._ec2 = ec2

    def client(self, *a, **k):
        return self._ec2


class _Ec2:
    def __init__(self, exc=None):
        self._exc = exc

    def describe_availability_zones(self):
        if self._exc:
            raise self._exc
        return {"AvailabilityZones": []}


def test_reachable_when_endpoint_answers():
    assert inventory.region_reachable(_Session(_Ec2()), "us-east-1") is True


def test_unreachable_on_connection_error():
    exc = EndpointConnectionError(endpoint_url="https://ec2.bad.amazonaws.com")
    assert inventory.region_reachable(_Session(_Ec2(exc)), "ap-bad-1") is False


def test_reachable_when_endpoint_returns_client_error():
    # AccessDenied etc. — endpoint is up; a collector deals with perms, region isn't skipped.
    exc = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "DescribeAvailabilityZones")
    assert inventory.region_reachable(_Session(_Ec2(exc)), "us-west-2") is True
