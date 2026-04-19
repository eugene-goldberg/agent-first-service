from agent_protocol.catalog import Capability, build_catalog


def test_catalog_contains_capabilities_and_metadata():
    caps = [
        Capability(
            intent="create a new project",
            method="POST",
            path="/projects",
            example_body={"name": "My Project", "description": "..."},
            returns="Project resource",
        ),
        Capability(
            intent="list projects",
            method="GET",
            path="/projects",
            returns="list of Project resources",
        ),
    ]

    doc = build_catalog(
        service="Projects",
        description="Create and manage projects, tasks, and milestones.",
        capabilities=caps,
        related=["/projects", "/tasks"],
    )

    assert doc["service"] == "Projects"
    assert doc["description"].startswith("Create and manage")
    assert len(doc["capabilities"]) == 2
    assert doc["capabilities"][0]["method"] == "POST"
    assert doc["capabilities"][0]["example_body"] == {
        "name": "My Project",
        "description": "...",
    }
    assert "example_body" not in doc["capabilities"][1]  # not supplied
    assert doc["_self"] == "/"
    assert doc["_related"] == ["/projects", "/tasks"]
