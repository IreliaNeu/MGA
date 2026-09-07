from __future__ import annotations

import copy

import pytest

from mga.human_validity import analyze, rater_agreement, summarize, validate_rows


def rows():
    return [
        {
            "scene_id": scene,
            "item_id": scene + str(label),
            "dimension": "direction",
            "split": "test",
            "caption_sha256": "a" * 64,
            "human_status": "rated",
            "human_score": label,
            "human_binary": label,
            "scores": {"good": float(label), "bad": float(1 - label)},
        }
        for scene in ("one", "two", "three")
        for label in (0, 1)
    ]


SPECS = {"good": {"direction": 1, "threshold": 0.5}, "bad": {"direction": 1, "threshold": 0.5}}


def test_perfect_reverse_and_paired_bootstrap():
    data = analyze(rows(), SPECS, replicates=12)
    common = data["dimensions"]["direction"]["common_support"]
    assert common["point_estimates"]["good"]["roc_auc"] == 1
    assert common["point_estimates"]["bad"]["roc_auc"] == 0
    for stat in ("roc_auc", "balanced_accuracy", "pairwise_accuracy_scene_macro"):
        assert common["paired_differences"]["good_minus_bad"][stat]["percentile_95ci"] == [1, 1]
    assert common["point_estimates"]["good"]["kendall_tau_b"] == pytest.approx(1)
    assert analyze(rows(), SPECS, replicates=12) == data


def test_missing_scores_compare_only_common_targets():
    data = rows()
    data[0]["scores"]["bad"] = None
    result = analyze(data, SPECS, replicates=4)["dimensions"]["direction"]
    assert result["per_metric_available"]["good"]["n_scored"] == 6
    assert result["per_metric_available"]["bad"]["n_scored"] == 5
    assert result["common_support"]["n"] == 5
    assert result["common_support"]["point_estimates"]["good"]["n_scored"] == 5


def test_unknown_human_target_does_not_become_negative():
    data = rows()
    data[0].update(human_status="unverifiable", human_score=None, human_binary=None)
    result = analyze(data, SPECS, replicates=2)["dimensions"]["direction"]
    assert result["human_status_counts"]["unverifiable"] == 1
    assert result["per_metric_available"]["good"]["negative"] == 2


@pytest.mark.parametrize("change", ["leak", "duplicate", "caption", "nan", "missing_metric"])
def test_rejects_invalid_alignment(change):
    data = rows()
    if change == "leak":
        data[0]["split"] = "dev"
    elif change == "duplicate":
        data.append(copy.deepcopy(data[0]))
    elif change == "caption":
        extra = dict(data[0], dimension="entity", caption_sha256="b" * 64)
        data.append(extra)
    elif change == "nan":
        data[0]["scores"]["good"] = float("nan")
    else:
        del data[0]["scores"]["good"]
    with pytest.raises(ValueError):
        validate_rows(data, SPECS, "test")


def test_ties_and_lower_is_better():
    data = rows()
    result = summarize(data, "bad", {"direction": -1, "threshold": 0.5})
    assert result["roc_auc"] == result["balanced_accuracy"] == 1
    for row in data:
        row["scores"]["good"] = 0.5
    tied = summarize(data, "good", SPECS["good"])
    assert tied["roc_auc"] == tied["pairwise_accuracy_scene_macro"] == 0.5
    assert tied["spearman_rho"] is None
    assert tied["kendall_tau_b"] is None


def test_ordinal_target_is_not_implicitly_binarized():
    data = rows()
    for row in data:
        row["human_score"] = 1 + 4 * row["human_score"]
        row["human_binary"] = None
    result = analyze(data, SPECS, replicates=2)["dimensions"]["direction"]
    assert result["per_metric_available"]["good"]["roc_auc"] is None
    assert result["per_metric_available"]["good"]["spearman_rho"] == pytest.approx(1)


def test_single_scene_has_no_bootstrap_confidence_interval():
    result = analyze(rows()[:2], SPECS, replicates=2)["dimensions"]["direction"]
    interval = result["common_support"]["bootstrap"]["good"]["roc_auc"]
    assert interval["valid_replicates"] == 0
    assert interval["percentile_95ci"] is None


def test_nominal_alpha_accounts_for_rater_missingness_and_unknowns():
    consensus = rows()
    votes = [
        dict(row, rater_id=str(rater), rating=row["human_binary"])
        for row in consensus
        for rater in range(3)
    ]
    result = rater_agreement(votes, consensus, split="test")["direction"]
    assert result["krippendorff_alpha_nominal"] == 1
    votes[0]["rating"] = "unverifiable"
    votes[1]["rating"] = "not_applicable"
    result = rater_agreement(votes, consensus, split="test")["direction"]
    assert result["usable_votes"] == 17
    assert result["category_counts"]["unverifiable"] == 1
    assert result["krippendorff_alpha_nominal"] < 1
    with pytest.raises(ValueError, match="Duplicate vote"):
        rater_agreement(votes + [votes[0]], consensus, split="test")
