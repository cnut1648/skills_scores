import numpy as np
import pandas as pd
import nltk
import matplotlib.pyplot as plt
import re
import string
from collections import Counter, defaultdict
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer


def text_cleanser(text: str):
    text = text.lower()
    # remove url
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', "", text)
    # remove [...]
    text = re.sub('\[.*?\]', '', text)
    # remove digits
    text = re.sub('\d+', '', text)
    # remove words with digit
    text = re.sub('\w*\d\w*', '', text)
    # remove punctutation
    text = re.sub('[%s]' % re.escape(string.punctuation), '', text)
    text = re.sub('[‘’“”…]', '', text)
    # remove newline
    text = re.sub('\n', '', text)
    # sub multiple space -> one space
    text = re.sub('\s+', ' ', text)
    return text


def cleansing(jobs: pd.Series, index: pd.Index, output_path):
    jobs = jobs.apply(text_cleanser)
    cv = CountVectorizer(stop_words=stopwords.words("english"))
    data_cv = cv.fit_transform(jobs)
    df = pd.DataFrame(
        data_cv.toarray(),
        columns=cv.get_feature_names(),
        index=index
    )
    df.to_hdf(output_path, key="cv", mode='w')
    return df


def tech_skills_or_having_scores(edge):
    return any(tech in edge.competency.categories for tech in ["Tech Skills", 'Tools']) \
           or any(c.startswith("IM-") for c in edge.competency.categories)


class USAJobsCollection:
    def __init__(self, postings: dict):
        """{'idx": {job info}"""
        self.postings = postings

    def __iter__(self):
        for id, job_info in self.postings.items():
            d = {
                "description": job_info["QualificationSummary"],
                # "experienceRequirements": ser["Level"],
                "id": id,
                "@type": "JobPosting",
                "title": job_info["PositionTitle"]
            }
            yield d

    def __len__(self):
        return len(self.postings)


class DFJobPostingCollection:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def __iter__(self):
        for idx, ser in self.df.iterrows():
            d = {
                "description": ser["JobDescription"],
                # "experienceRequirements": ser["Level"],
                "id": idx,
                "@type": "JobPosting",
                "title": ser["Title"]
            }
            yield d

    def __len__(self):
        i = len(self.df)
        return i


def extract_skills_from(sample, skill_extractor):
    data = defaultdict(dict)
    for s in sample:
        for i in skill_extractor.candidate_skills(s):
            d = data[i.matched_skill_identifier]
            for cat in i.skill_cat:
                if cat.startswith("IM-"):
                    d["score"] = float(cat[3:])
                else:
                    d["cat"] = cat
            d["count"] = d.get("count", 0) + 1
            d["skills"] = i.skill_name
    return data


def merge_extracted_skills(*datas):
    if not datas:
        return {}
    ret = datas[0]
    for data in datas[1:]:
        for id, d in data.items():
            if id not in ret:
                ret[id] = d
            else:
                ret[id]['count'] += d['count']
    return ret


def extract_competency(competency):
    # having IM scores
    if any("-" in cat for cat in competency.categories):
        for cat in competency.categories:
            if "-" in cat:
                score = float(cat.split("-")[1])
            else:
                category = cat
    # tech skills
    else:
        # baseline scores
        score = 2
        for cat in competency.categories:
            if cat == "HOT":
                score = 4
            elif cat in ["Tools", "Tech Skills"]:
                category = cat

    return competency.identifier, competency.name, category, score, 0


def skills_from_USAJobs(ontology, usaJobs: dict, skill_extractor, alpha=1):
    data = merge_extracted_skills(
        *[
            extract_skills_from(sample=USAJobsCollection(job),
                                skill_extractor=skill_extractor)
            for job in usaJobs.values()
        ]
    )
    print(f"unique skills {len(data)} in total {sum(v['count'] for v in data.values())} skills")
    df = pd.DataFrame(
        [extract_competency(comp) for comp in ontology.competencies],
        columns=["id", "name", "cat", "score", "count"]
    )
    df = df.set_index("id")
    for id, skill in data.items():
        df.loc[id, "count"] = skill["count"]

    total_counts = df["count"].sum()
    df["prob"] = df.apply(lambda row: row["count"] / total_counts, axis=1)

    num_S = len(ontology._competency_occupation_edges)
    df["smoothed"] = df.apply(
        lambda row: (row["count"] + alpha) / (total_counts + alpha * num_S), axis=1)
    df["max_divide"] = df.apply(
        lambda row: row["count"] / df["count"].max(), axis=1)
    df["max_divide_smoothed"] = df.apply(
        lambda row: (row["count"] + alpha) / (df["count"].max() + alpha * num_S), axis=1)
    df["min_divide_smoothed"] = df.apply(
        lambda row: (row["count"] + alpha) / (df["count"].min() + alpha * num_S), axis=1)
    df["log_smoothed"] = df.apply(
        lambda row: np.log10((row["count"] + alpha) / (df["count"].min() + alpha * num_S)), axis=1)
    df.sort_values(by="count").tail(5)
    return df


def calculate_new_score(row, df, prob="smoothed"):
    new_score = row["score"]
    tech_cat = ["Tools", "Tech Skills"]
    tech = df["cat"].isin(tech_cat)
    cur = df[tech] if row["cat"] in tech_cat else df[~tech]
    min_prob, max_prob = cur[prob].min(), cur[prob].nlargest(10).iloc[5]
    prob = min(row[prob], max_prob)
    weight = (prob - min_prob) * (1.5 - 0.5) / (max_prob - min_prob) + 0.5
    new_score = new_score * (0.9 + 0.1 * weight)
    return min(max(new_score, 1), 5)
