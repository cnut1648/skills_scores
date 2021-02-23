import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import pickle
import tqdm


class USAJobsFetcher(object):
    base_url = 'https://data.usajobs.gov/api/Search?'

    def __init__(self, auth_key, email, result_per_page=500, session=None):
        self.auth_key = auth_key
        self.key_email = email
        self.session = session
        self.result_per_page = result_per_page

    def __enter__(self):
        if not self.session:
            self.session = self._default_session()
            return self

    def __exit__(self, *unused):
        self.session.close()

    @property
    def headers(self):
        return {
            'Host': 'data.usajobs.gov',
            'User-Agent': self.key_email,
            'Authorization-Key': self.auth_key
        }

    def _default_session(self):
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    def _get_page_json(self, params: dict):
        response = self.session.get(
            self.base_url,
            params=params,
            headers=self.headers,
            timeout=5
        )
        return response.json()

    def _search_result(self, job=None, page_num=1):
        params = {'ResultsPerPage': self.result_per_page, 'Page': page_num}
        params.update({} if not job else {"PositionTitle": job})

        return self._get_page_json(params)['SearchResult']

    def _result_items(self, result):
        return result['SearchResultItems']

    def _number_of_pages(self, result):
        return int(result['UserArea']['NumberOfPages'])

    def _job_postings(self, job: str = None) -> dict:
        result = self._search_result(job, page_num=1)
        all_postings = self._result_items(result)
        pages = self._number_of_pages(result)
        for page in tqdm.trange(2, pages + 1):
            result = self._search_result(job, page)
            all_postings += self._result_items(result)

        # deduplicated
        lookup = {}
        ct = 0
        for posting in all_postings:
            ctlnum = posting['MatchedObjectId']
            if ctlnum in lookup:
                ct += 1

            # update new one
            lookup[ctlnum] = posting['MatchedObjectDescriptor']
        print('found duplicate', ct)
        print("found job postings", len(lookup))
        return lookup

    def all_postings_of(self, jobs: [str] = None):
        if not jobs:
            return self._job_postings()
        return {
            job: self._job_postings(job)
            for job in jobs
        }



if __name__ == "__main__":
    fetcher = USAJobsFetcher("jqKffppjkpApPrlwNpgSpVd4B97XI3f3yOCWemycJEM=", "jiashuxu@usc.edu")
    jobs = ['Administrative Services Managers', 'Business Manager']
    jobpostings = fetcher.all_postings_of(jobs)
    jobs = [
        "_".join(job.split(" "))
        for job in jobs
    ]
    with open(f"db/USAJobs-{'&'.join(jobs)}.pkl", "wb") as f:
        pickle.dump(jobpostings, f)
