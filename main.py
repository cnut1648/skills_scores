import concurrent
from argparse import ArgumentParser
from time import time
from datetime import date
from typing import List
from utils import OnetWebService
import sys
from updateScores import updateScores
from collections import defaultdict


def check_for_error(service_result):
    if 'error' in service_result:
        sys.exit(service_result['error'])


def main(jobs: List[str],
         skill_extractor: str = "exact_match",
         alpha: float = 1.0,
         based_prob: str = "smoothed"
         ):
    onet_api = OnetWebService(
        "university_of_southe",
        "9228tmx"
    )
    version_info = onet_api.call("about")
    check_for_error(version_info)
    print(f"Using ONet service (version {version_info['api_version']}) to fetch onet id")

    id_jobs = defaultdict(list)
    for job in jobs:
        keyword_result = onet_api.call("online/search", ("keyword", job))
        check_for_error(keyword_result)
        if ('occupation' not in keyword_result) or (0 == len(keyword_result['occupation'])):
            print(f"No relevant occupations were found for job {job}, continuing..")
        else:
            id = keyword_result["occupation"][0]["code"]
            title = keyword_result["occupation"][0]['title']
            confidence = keyword_result["occupation"][0]['relevance_score']
            print(f"{job}'s id: {id}, corresponding job category: {title}, confidence score: {confidence}")

            id_jobs[id].append(job)

    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        tasks = {
            executor.submit(updateScores,
                jobs,
                id,
                skill_extractor,
                alpha,
                based_prob
            ): id for id, jobs in id_jobs.items()
        }
        for future in concurrent.futures.as_completed(tasks):
            id = tasks[future]
            try:
                df = future.result()
                if df is not None:
                    df.to_csv(f"scores-{id}::{date.today()}.csv")
            except Exception as e:
                print(e)
                return


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("jobs", type=str, nargs="+",
                        help="list of jobs that you want to fetch job postings and update scores")
    parser.add_argument("--extractor", dest="skill_extractor",
                        type=str, nargs="?", default="exact_match",
                        help="type of skill extractor for extracting skills from jobpostings, either 'exact_match' or "
                             "'fuzzy_search'")
    parser.add_argument("--alpha", type=float,
                        nargs="?", help="alpha in add-alpha smoothing, default = 1.0",
                        default=1.0)
    parser.add_argument("--prob", dest="based_prob", nargs="?", default="smoothed",
                        help="use which prob to update the scores, must be 'smoothed' | 'max_divide' | "
                             "'max_divide_smoothed' | 'min_divide_smoothed' | 'log_smoothed' "
                        )
    args = parser.parse_args()

    start = time()
    main(
        jobs=args.jobs,
        skill_extractor=args.skill_extractor,
        alpha=args.alpha,
        based_prob=args.based_prob
    )
    print("Updating for scores took %.3f seconds" % (time() - start))
