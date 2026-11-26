"""Private/public citizen connector paths and identity behavior."""

from client.citizen_connector import HttpCitizenReportConnector


class Transport:
    def __init__(self):
        self.calls = []

    def get_json(self, path, query=None, *, requires_identity=False):
        self.calls.append((path, query, requires_identity))
        return self.calls[-1]


def test_private_and_public_query_paths_encode_codes_and_cursors() -> None:
    transport = Transport()
    connector = HttpCitizenReportConnector(transport)
    connector.list_my_reports(20, "opaque+/=")
    connector.get_my_report("SGF.OLD-1")
    connector.list_my_report_history("SGF.OLD-1", 50, "hist+/=")
    connector.get_public_report("LEGACY_1")
    assert transport.calls == [
        ("/tickets/citizen/mine", {"limit": 20, "cursor": "opaque+/="}, True),
        ("/tickets/citizen/mine/SGF.OLD-1", None, True),
        ("/tickets/citizen/mine/SGF.OLD-1/history", {"limit": 50, "cursor": "hist+/="}, True),
        ("/tickets/public/LEGACY_1", None, False),
    ]
