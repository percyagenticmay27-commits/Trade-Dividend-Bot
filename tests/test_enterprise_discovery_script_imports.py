import runpy


def test_collector_script_can_import_host_modules_when_executed_by_path():
    namespace = runpy.run_path("scripts/collect_enterprise_discovery_sources.py", run_name="not_main")
    assert callable(namespace["main"])


def test_generator_script_can_import_host_modules_when_executed_by_path():
    namespace = runpy.run_path("scripts/generate_enterprise_weekly_market_discovery.py", run_name="not_main")
    assert callable(namespace["main"])
