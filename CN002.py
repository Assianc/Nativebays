import jieba
from itertools import islice
from tqdm.contrib.itertools import product
from sklearn.model_selection import train_test_split
from tqdm import tqdm
from joblib import Parallel, delayed
import itertools
import os
import time
import numpy as np
import time
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.base import BaseEstimator, ClassifierMixin


class SimpleSPODE(BaseEstimator, ClassifierMixin):
    def __init__(self, alpha=1.0):
        self.alpha = alpha  # 拉普拉斯平滑参数
        self.feature_probs = {}
        self.class_probs = {}
        self.parent = None

    def fit(self, X, y):
        self.classes, class_counts = np.unique(y, return_counts=True)
        self.class_probs = {c: count / len(y) for c, count in zip(self.classes, class_counts)}

        # 选择特定特征作为父特征（简单起见，选择第一个特征）
        self.parent = 0
        self.feature_probs = {c: {} for c in self.classes}

        for c in self.classes:
            X_c = X[y == c]
            parent_vals, parent_counts = np.unique(X_c[:, self.parent], return_counts=True)
            parent_probs = {val: (count + self.alpha) / (len(X_c) + self.alpha * len(parent_vals))
                            for val, count in zip(parent_vals, parent_counts)}
            self.feature_probs[c][self.parent] = parent_probs

            for feature in range(X.shape[1]):
                if feature == self.parent:
                    continue
                self.feature_probs[c][feature] = {}
                for parent_val in parent_vals:
                    X_parent = X_c[X_c[:, self.parent] == parent_val]
                    feature_vals, feature_counts = np.unique(X_parent[:, feature], return_counts=True)
                    self.feature_probs[c][feature][parent_val] = {
                        val: (count + self.alpha) / (len(X_parent) + self.alpha * len(feature_vals))
                        for val, count in zip(feature_vals, feature_counts)}

    def predict(self, X):
        predictions = []
        for x in X:
            class_probs = {c: np.log(self.class_probs[c]) for c in self.classes}
            parent_val = x[self.parent]
            for c in self.classes:
                parent_prob = self.feature_probs[c][self.parent].get(parent_val, self.alpha / (
                            sum(self.feature_probs[c][self.parent].values()) + self.alpha))
                for feature in range(X.shape[1]):
                    if feature == self.parent:
                        continue
                    feature_val = x[feature]
                    feature_prob = self.feature_probs[c][feature].get(parent_val, {}).get(feature_val, self.alpha / (
                                sum(self.feature_probs[c][feature].get(parent_val, {}).values()) + self.alpha))
                    class_probs[c] += np.log(parent_prob * feature_prob)
            predictions.append(max(class_probs, key=class_probs.get))
        return predictions

    def set_params(self, **params):
        for key, value in params.items():
            setattr(self, key, value)
        return self


# 简单朴素贝叶斯分类器
class SimpleNaiveBayes:
    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y):
        n_samples, n_features = X.shape
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)

        self.class_log_prior_ = np.zeros(n_classes)
        self.feature_log_prob_ = np.zeros((n_classes, n_features))

        for idx, c in enumerate(self.classes_):
            X_c = X[y == c]
            self.class_log_prior_[idx] = np.log(X_c.shape[0] / n_samples)
            self.feature_log_prob_[idx] = np.log((X_c.sum(axis=0) + self.alpha) / (X_c.sum() + self.alpha * n_features))

    def predict(self, X):
        jll = X @ self.feature_log_prob_.T + self.class_log_prior_
        return self.classes_[np.argmax(jll, axis=1)]

    def score(self, X, y):
        return np.mean(self.predict(X) == y)

    def get_params(self, deep=True):
        return {"alpha": self.alpha}

    def set_params(self, **params):
        for key, value in params.items():
            setattr(self, key, value)
        return self


class SimpleCountVectorizer:
    def __init__(self, max_df=1.0, min_df=1):
        self.vocabulary_ = {}
        self.feature_names_ = []
        self.max_df = max_df
        self.min_df = min_df

    def fit(self, raw_documents):
        vocab = {}
        doc_count = {}
        total_docs = len(raw_documents)

        for doc in raw_documents:
            words = set(doc)  # 使用 jieba 分词
            for word in words:
                if word not in vocab:
                    vocab[word] = len(vocab)
                    doc_count[word] = 1
                else:
                    doc_count[word] += 1

        # 过滤词汇
        self.vocabulary_ = {word: idx for word, idx in vocab.items()
                            if self.min_df <= doc_count[word] <= self.max_df * total_docs}
        self.feature_names_ = list(self.vocabulary_.keys())
        return self

    def transform(self, raw_documents):
        rows = []
        for doc in raw_documents:
            words = set(doc)  # 使用 jieba 分词
            row = [0] * len(self.vocabulary_)
            for word in words:
                if word in self.vocabulary_:
                    row[self.vocabulary_[word]] += 1
            rows.append(row)
        return np.array(rows)

    def fit_transform(self, raw_documents):
        self.fit(raw_documents)
        return self.transform(raw_documents)

    def get_params(self, deep=True):
        return {"max_df": self.max_df, "min_df": self.min_df}

    def set_params(self, **params):
        for key, value in params.items():
            setattr(self, key, value)
        return self


import numpy as np
from collections import defaultdict
import math
from tqdm import tqdm


class SimpleTfidfVectorizer:
    def __init__(self, max_df=1.0, min_df=1, stop_words=None):
        self.max_df = max_df
        self.min_df = min_df
        self.stop_words = stop_words if stop_words else []
        self.vocab = {}
        self.idf = {}

    def fit(self, documents):
        # 计算词频（TF）
        doc_count = len(documents)
        term_doc_count = defaultdict(int)

        for doc in tqdm(documents, desc="计算词频"):
            tf_doc = defaultdict(int)
            words = set(doc)
            for word in words:
                if word not in self.stop_words:
                    tf_doc[word] += 1
            for word in tf_doc.keys():
                term_doc_count[word] += 1

        # 构建词汇表
        self.vocab = {word: idx for idx, (word, count) in enumerate(term_doc_count.items())
                      if self.min_df <= count <= self.max_df * doc_count}

        # 计算逆文档频率（IDF）
        self.idf = {word: math.log(doc_count / (count + 1)) + 1 for word, count in term_doc_count.items() if
                    word in self.vocab}

    def transform(self, documents):
        tfidf = np.zeros((len(documents), len(self.vocab)))
        for doc_idx, doc in tqdm(enumerate(documents), desc="计算TF-IDF"):
            words = set(doc)
            tf_doc = defaultdict(int)
            for word in words:
                if word in self.vocab:
                    tf_doc[word] += 1
            for word, count in tf_doc.items():
                if word in self.vocab:
                    tfidf[doc_idx, self.vocab[word]] = count * self.idf[word]
        return tfidf

    def fit_transform(self, documents):
        self.fit(documents)
        return self.transform(documents)


class SimpleGridSearchCV:
    def __init__(self, estimator, param_grid, cv=5, n_jobs=-1):
        self.estimator = estimator
        self.param_grid = param_grid
        self.cv = cv
        self.n_jobs = n_jobs
        self.best_params_ = None
        self.best_score_ = None
        self.cv_results_ = []

    def fit(self, X, y):
        self.best_score_ = -np.inf
        self.best_params_ = None

        param_combinations = list(self._param_iterator(self.param_grid))

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(self._evaluate_params)(params, X, y) for params in tqdm(param_combinations, desc="Grid Search")
        )

        for params, avg_score in results:
            self.cv_results_.append({'params': params, 'score': avg_score})
            if avg_score > self.best_score_:
                self.best_score_ = avg_score
                self.best_params_ = params

        # 保存结果到文件
        self._save_results_to_file()

    def _evaluate_params(self, params, X, y):
        scores = []
        for fold in range(self.cv):

            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=1 / self.cv, random_state=fold)
            model = self.estimator.set_params(**params)
            model.fit(X_train, y_train)
            scores.append(model.score(X_val, y_val))
        avg_score = np.mean(scores)
        return params, avg_score

    def _param_iterator(self, param_grid):
        keys = param_grid.keys()
        values = (param_grid[key] for key in keys)
        for combination in itertools.product(*values):
            yield dict(zip(keys, combination))

    def _save_results_to_file(self):
        os.makedirs('result', exist_ok=True)
        with open('result/cv_results.txt', 'w', encoding='utf-8') as file:
            for result in self.cv_results_:
                file.write(f"Params: {result['params']}, Score: {result['score']}\n")


def load_stop_words(filename):
    """
    加载停用词列表
    """
    stop_words = set()
    with open(f'./data/cnsmss/{filename}.txt', 'r', encoding='utf-8') as file:
        for line in file:
            stop_words.add(line.strip())
    return stop_words


class SimpleHalvingGridSearchCV:
    def __init__(self, estimator, param_grid, cv=5, factor=3, min_resources='exhaust', n_jobs=-1):
        self.estimator = estimator
        self.param_grid = param_grid
        self.cv = cv
        self.factor = factor
        self.min_resources = min_resources
        self.n_jobs = n_jobs
        self.best_params_ = None
        self.best_score_ = None
        self.cv_results_ = []

    def fit(self, X, y):
        self.best_score_ = -np.inf
        self.best_params_ = None

        param_combinations = list(self._param_iterator(self.param_grid))
        n_candidates = len(param_combinations)
        print(f"参数组合数量: {n_candidates}")

        # 初始资源数
        n_resources = len(X) if self.min_resources == 'exhaust' else self.min_resources
        if isinstance(n_resources, str) and n_resources == 'exhaust':
            n_resources = max(len(X) // self.factor, 1)
        print(f"初始资源数量: {n_resources}")

        while n_candidates > 1 and n_resources <= len(X):
            print(f"评估 {n_candidates} 个候选参数，每个使用 {n_resources} 个资源。")
            results = Parallel(n_jobs=self.n_jobs)(
                delayed(self._evaluate_params)(params, X, y, n_resources) for params in param_combinations
            )

            # 按得分排序，选择得分最好的前1/factor个参数组合
            results.sort(key=lambda x: x[1], reverse=True)
            n_candidates = max(1, n_candidates // self.factor)
            param_combinations = [params for params, score in results[:n_candidates]]

            for result in results:
                self.cv_results_.append({'params': result[0], 'score': result[1]})

            n_resources = min(len(X), n_resources * self.factor)

            if results[0][1] > self.best_score_:
                self.best_score_ = results[0][1]
                self.best_params_ = results[0][0]

        print(f"最佳得分: {self.best_score_}")
        print(f"最佳参数: {self.best_params_}")

        # 保存结果到文件
        self._save_results_to_file()

    def _evaluate_params(self, params, X, y, n_resources):
        scores = []
        for fold in range(self.cv):
            X_train, X_val, y_train, y_val = train_test_split(X[:n_resources], y[:n_resources], test_size=1 / self.cv,
                                                              random_state=fold)
            model = self.estimator.set_params(**params)
            model.fit(X_train, y_train)
            scores.append(model.score(X_val, y_val))
        avg_score = np.mean(scores)
        return params, avg_score

    def _param_iterator(self, param_grid):
        keys = param_grid.keys()
        values = (param_grid[key] for key in keys)
        for combination in product(*values):
            yield dict(zip(keys, combination))

    def _save_results_to_file(self):
        os.makedirs('result', exist_ok=True)
        with open('result/cv_results.txt', 'w') as f:
            for result in self.cv_results_:
                f.write(f"Params: {result['params']}, Score: {result['score']}\n")


def loadCNDataSet(lines, stop_words, sample_size=None):
    """
    读取中文数据集并下采样
    :return:
    """
    docs = []  # 存储文本
    labels = []  # 存储标签

    try:
        with open('./data/cnsmss/80w.txt', 'r', encoding='utf-8') as file:
            dataSet = [line.strip().split('\t') for line in islice(file, lines)]
    except:
        # GitHub action
        with open('naivebayes/data/cnsmss/80w.txt', 'r', encoding='utf-8') as file:
            dataSet = [line.strip().split('\t') for line in islice(file, lines)]

    for item in tqdm(dataSet, desc='加载数据集：'):
        # 0：非垃圾短信；1：垃圾短信
        labels.append(int(item[1]))

        # 将每条短信拆分为单词列表
        try:
            words = jieba.lcut(item[2], cut_all=False)
            # 去除空格
            words = [word for word in words if word != ' ' and word not in stop_words]
            docs.append(words)
        except IndexError as e:
            print('\n', e)
            pass

    if sample_size:
        from collections import Counter
        import random

        # 下采样
        counter = Counter(labels)
        min_class = min(counter, key=counter.get)
        min_count = counter[min_class]

        if sample_size > min_count:
            sample_size = min_count

        sampled_docs = []
        sampled_labels = []

        for label in set(labels):
            label_docs = [doc for doc, l in zip(docs, labels) if l == label]
            sampled_docs.extend(random.sample(label_docs, sample_size))
            sampled_labels.extend([label] * sample_size)

        docs = sampled_docs
        labels = sampled_labels


    return docs, labels


if __name__ == '__main__':
    # 测试nativeBayesCN
    stop_words = load_stop_words()
    listOposts, listClasses = loadCNDataSet(5000)
    print("Data loaded.")
