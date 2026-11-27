class ServiceNowClient:
    def __init__(self, session):
        self.session = session

    def get(self, url, params=None):
        resp = self.session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp
