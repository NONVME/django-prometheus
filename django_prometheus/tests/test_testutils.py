#!/usr/bin/env python
import unittest
from operator import itemgetter

import prometheus_client

from django_prometheus.testutils import (
    assert_metric_diff,
    assert_metric_equal,
    assert_metric_no_diff,
    assert_metric_not_equal,
    get_metric,
    get_metric_from_frozen_registry,
    get_metrics_vector,
    save_registry,
)


class PrometheusTestCaseMixinTest(unittest.TestCase):
    def setUp(self):
        self.registry = prometheus_client.CollectorRegistry()
        self.some_gauge = prometheus_client.Gauge("some_gauge", "Some gauge.", registry=self.registry)
        self.some_gauge.set(42)
        self.some_labelled_gauge = prometheus_client.Gauge(
            "some_labelled_gauge",
            "Some labelled gauge.",
            ["labelred", "labelblue"],
            registry=self.registry,
        )
        self.some_labelled_gauge.labels("pink", "indigo").set(1)
        self.some_labelled_gauge.labels("pink", "royal").set(2)
        self.some_labelled_gauge.labels("carmin", "indigo").set(3)
        self.some_labelled_gauge.labels("carmin", "royal").set(4)

    def test_get_metric(self):
        """Tests get_metric."""
        assert 42 == get_metric("some_gauge", registry=self.registry)
        assert 1 == get_metric(
            "some_labelled_gauge",
            registry=self.registry,
            labelred="pink",
            labelblue="indigo",
        )

    def test_get_metrics_vector(self):
        """Tests get_metrics_vector."""
        vector = get_metrics_vector("some_nonexistent_gauge", registry=self.registry)
        assert [] == vector
        vector = get_metrics_vector("some_gauge", registry=self.registry)
        assert [({}, 42)] == vector
        vector = get_metrics_vector("some_labelled_gauge", registry=self.registry)
        assert sorted(
            [
                ({"labelred": "pink", "labelblue": "indigo"}, 1),
                ({"labelred": "pink", "labelblue": "royal"}, 2),
                ({"labelred": "carmin", "labelblue": "indigo"}, 3),
                ({"labelred": "carmin", "labelblue": "royal"}, 4),
            ],
            key=itemgetter(1),
        ) == sorted(vector, key=itemgetter(1))

    def test_assert_metric_equal(self):
        """Tests assert_metric_equal."""
        # First we test that a scalar metric can be tested.
        assert_metric_equal(42, "some_gauge", registry=self.registry)

        assert_metric_not_equal(43, "some_gauge", registry=self.registry)

        # Here we test that assert_metric_equal fails on nonexistent gauges.
        assert_metric_not_equal(42, "some_nonexistent_gauge", registry=self.registry)

        # Here we test that labelled metrics can be tested.
        assert_metric_equal(
            1,
            "some_labelled_gauge",
            registry=self.registry,
            labelred="pink",
            labelblue="indigo",
        )

        assert_metric_not_equal(
            1,
            "some_labelled_gauge",
            registry=self.registry,
            labelred="tomato",
            labelblue="sky",
        )

    def test_registry_saving(self):
        """Tests save_registry and frozen registries operations."""
        frozen_registry = save_registry(registry=self.registry)
        # Test that we can manipulate a frozen scalar metric.
        assert 42 == get_metric_from_frozen_registry("some_gauge", frozen_registry)
        self.some_gauge.set(99)
        assert 42 == get_metric_from_frozen_registry("some_gauge", frozen_registry)
        assert_metric_diff(frozen_registry, 99 - 42, "some_gauge", registry=self.registry)

        assert_metric_no_diff(frozen_registry, 1, "some_gauge", registry=self.registry)

        # Now test the same thing with a labelled metric.
        assert 1 == get_metric_from_frozen_registry(
            "some_labelled_gauge", frozen_registry, labelred="pink", labelblue="indigo"
        )
        self.some_labelled_gauge.labels("pink", "indigo").set(5)
        assert 1 == get_metric_from_frozen_registry(
            "some_labelled_gauge", frozen_registry, labelred="pink", labelblue="indigo"
        )
        assert_metric_diff(
            frozen_registry,
            5 - 1,
            "some_labelled_gauge",
            registry=self.registry,
            labelred="pink",
            labelblue="indigo",
        )

        assert_metric_no_diff(
            frozen_registry,
            1,
            "some_labelled_gauge",
            registry=self.registry,
            labelred="pink",
            labelblue="indigo",
        )
