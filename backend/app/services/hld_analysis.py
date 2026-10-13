"""Deterministic, citation-grounded extraction and comparison for HLD documents."""
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


UNSUPPORTED = "Insufficient evidence"
COMPONENT_HEADING = re.compile(
    r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(SWC_[A-Za-z0-9_]+)\b[^\r\n]*"
)
COMPONENT_REFERENCE = re.compile(r"\bSWC_[A-Za-z0-9_]+\b")
PORT_HEADING = re.compile(
    r"(?im)^\s*[-*]?\s*(Input|Output)\s+Port\s*:\s*([A-Za-z][A-Za-z0-9_]*)"
    r"(?:\s*\(Interface\s*:\s*([^)]+)\))?"
)


def _citation(chunk: Dict[str, Any], snippet: Optional[str] = None) -> Dict[str, Any]:
    return {
        "document_id": chunk.get("document_id"),
        "document_name": chunk.get("filename", "Unknown document"),
        "version": chunk.get("version_number", 1),
        "page": chunk.get("page_number"),
        "section": chunk.get("section_title") or None,
        "chunk_id": chunk.get("chunk_id"),
        "snippet": (snippet if snippet is not None else chunk.get("content", ""))[:500],
    }


def _unique_citations(chunks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found = {}
    for chunk in chunks:
        citation = _citation(chunk)
        found[citation["chunk_id"]] = citation
    return list(found.values())


def _field(pattern: str, text: str, flags: int = re.IGNORECASE | re.MULTILINE) -> Optional[str]:
    match = re.search(pattern, text, flags)
    return " ".join(match.group(1).strip().split()) if match else None


def _period(text: str) -> Optional[str]:
    return _field(
        r"(?:Execution\s+)?Period\s*[:=]\s*([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))"
        r"|execution\s+period\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))",
        text,
    ) or _period_second_group(text)


def _period_second_group(text: str) -> Optional[str]:
    match = re.search(
        r"execution\s+period\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))",
        text,
        re.IGNORECASE,
    )
    return " ".join(match.group(1).split()) if match else None


def _period_ms(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|msec|milliseconds?|s|sec|seconds?)\s*", value, re.I)
    if not match:
        return None
    number = float(match.group(1))
    return number * 1000 if match.group(2).lower().startswith("s") else number


def _build_source(chunks: List[Dict[str, Any]]) -> Tuple[str, List[Tuple[int, int, Dict[str, Any]]]]:
    parts = []
    spans = []
    cursor = 0
    for chunk in chunks:
        content = chunk.get("content", "")
        if not content:
            continue
        if parts:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(content)
        cursor += len(content)
        spans.append((start, cursor, chunk))
    return "".join(parts), spans


def _chunks_for_range(
    spans: List[Tuple[int, int, Dict[str, Any]]], start: int, end: int
) -> List[Dict[str, Any]]:
    return [chunk for left, right, chunk in spans if left < end and right > start]


def _component_records(
    chunks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    grouped: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        grouped[(chunk.get("document_id", 0), chunk.get("version_number", 1))].append(chunk)

    records: Dict[str, Dict[str, Any]] = {}
    for source_chunks in grouped.values():
        text, spans = _build_source(source_chunks)
        headings = list(COMPONENT_HEADING.finditer(text))
        for index, heading in enumerate(headings):
            name = heading.group(1)
            start = heading.start()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            block = text[start:end]
            block_chunks = _chunks_for_range(spans, start, end) or _chunks_for_range(spans, start, heading.end())
            record = records.setdefault(name, {
                "component_name": name,
                "component_type": UNSUPPORTED,
                "functions": [],
                "execution_period": UNSUPPORTED,
                "ports": [],
                "citations": [],
            })
            component_type = _field(r"Component\s+Type\s*:\s*([^\r\n]+)", block)
            if component_type:
                record["component_type"] = component_type
            function = _field(
                r"Function\s*:\s*(.+?)(?=\n\s*(?:[-*]\s*)?(?:Input\s+Port|Output\s+Port|Component\s+Type|Execution\s+Period)\s*:|\Z)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if function:
                function = " ".join(function.split())
                if function not in record["functions"]:
                    record["functions"].append(function)
            execution_period = _period(block)
            if execution_period:
                record["execution_period"] = execution_period
            record["citations"].extend(_unique_citations(block_chunks))

            port_matches = list(PORT_HEADING.finditer(block))
            for port_index, port_match in enumerate(port_matches):
                port_end = port_matches[port_index + 1].start() if port_index + 1 < len(port_matches) else len(block)
                port_text = block[port_match.end():port_end]
                port_citations = _unique_citations(
                    _chunks_for_range(spans, start + port_match.start(), start + port_end)
                ) or _unique_citations(block_chunks)
                transmission_period = _field(
                    r"(?:transmission\s+period(?:icity)?|output\s+rate|rate)\s*(?:is\s+configured\s+to\s*)?[:=]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))",
                    port_text,
                )
                if not transmission_period:
                    transmission_period = _period(port_text)
                expected_period_match = re.search(
                    r"(?:requires?|expects?|expectation)[^\r\n]*?\b([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))",
                    port_text,
                    re.IGNORECASE,
                )
                expected_period = (
                    " ".join(expected_period_match.group(1).split()) if expected_period_match else None
                )
                record["ports"].append({
                    "component": name,
                    "direction": port_match.group(1).lower(),
                    "port_name": port_match.group(2),
                    "interface_name": (
                        (
                            (port_match.group(3) or "").split("(", 1)[0].strip()
                            or _field(r"Interface\s*:\s*([^\r\n)]+)", port_text)
                            or UNSUPPORTED
                        ).split("(", 1)[0].strip()
                    ),
                    "protocol": _field(
                        r"(?:Protocol|Transmission\s+Medium)\s*:\s*([^\r\n]+)", port_text
                    ) or UNSUPPORTED,
                    "data_type": _field(r"(?:Data\s+Type|Signal)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", port_text)
                    or UNSUPPORTED,
                    "transmission_period": transmission_period or UNSUPPORTED,
                    "expected_period": expected_period or UNSUPPORTED,
                    "citations": port_citations,
                })
            for inline_interface in re.finditer(
                r"\bInterface\s+(IF_[A-Za-z0-9_]+)\s+output\s+rate\s*:\s*"
                r"(?:Synchronized\s+to\s*)?([0-9]+(?:\.[0-9]+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?))",
                block,
                re.IGNORECASE,
            ):
                rate_chunks = _unique_citations(
                    _chunks_for_range(
                        spans,
                        start + inline_interface.start(),
                        start + inline_interface.end(),
                    )
                ) or _unique_citations(block_chunks)
                record["ports"].append({
                    "component": name,
                    "direction": "output",
                    "port_name": UNSUPPORTED,
                    "interface_name": inline_interface.group(1),
                    "protocol": UNSUPPORTED,
                    "data_type": UNSUPPORTED,
                    "transmission_period": " ".join(inline_interface.group(2).split()),
                    "expected_period": UNSUPPORTED,
                    "citations": rate_chunks,
                })

    # Include explicitly named components that appear in a documented flow but have
    # no component detail section; their details remain visibly unsupported.
    for chunk in chunks:
        for name in COMPONENT_REFERENCE.findall(chunk.get("content", "")):
            records.setdefault(name, {
                "component_name": name,
                "component_type": UNSUPPORTED,
                "functions": [],
                "execution_period": UNSUPPORTED,
                "ports": [],
                "citations": [_citation(chunk)],
            })

    for record in records.values():
        record["functions"] = record["functions"] or [UNSUPPORTED]
        record["citations"] = list({c["chunk_id"]: c for c in record["citations"]}.values())
    return list(records.values()), records


def _matrix_and_edges(
    components: List[Dict[str, Any]], chunks: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ports = [port for component in components for port in component["ports"]]
    outputs = [port for port in ports if port["direction"] == "output"]
    inputs = [port for port in ports if port["direction"] == "input"]
    matrix = []
    edges = []
    for output in outputs:
        targets = [
            port for port in inputs
            if output["interface_name"] != UNSUPPORTED
            and output["interface_name"] == port["interface_name"]
        ]
        if not targets:
            targets = [None]
        for target in targets:
            citations = output["citations"] + (target["citations"] if target else [])
            matrix.append({
                "source_component": output["component"],
                "target_component": target["component"] if target else UNSUPPORTED,
                "interface_name": output["interface_name"],
                "output_port": output["port_name"],
                "input_port": target["port_name"] if target else UNSUPPORTED,
                "protocol": output["protocol"],
                "target_protocol": target["protocol"] if target else UNSUPPORTED,
                "data_type": output["data_type"],
                "input_data_type": target["data_type"] if target else UNSUPPORTED,
                "transmission_period": output["transmission_period"],
                "expected_period": target["expected_period"] if target else UNSUPPORTED,
                "citations": citations,
            })
            if target:
                edges.append({
                    "source": output["component"],
                    "target": target["component"],
                    "interface_name": output["interface_name"],
                    "evidence_type": "matched documented output/input interface",
                    "citations": citations,
                })

    for input_port in inputs:
        has_sender = any(
            output["interface_name"] != UNSUPPORTED
            and output["interface_name"] == input_port["interface_name"]
            for output in outputs
        )
        if has_sender:
            continue
        matrix.append({
            "source_component": UNSUPPORTED,
            "target_component": input_port["component"],
            "interface_name": input_port["interface_name"],
            "output_port": UNSUPPORTED,
            "input_port": input_port["port_name"],
            "protocol": UNSUPPORTED,
            "target_protocol": input_port["protocol"],
            "data_type": UNSUPPORTED,
            "input_data_type": input_port["data_type"],
            "transmission_period": UNSUPPORTED,
            "expected_period": input_port["expected_period"],
            "citations": input_port["citations"],
        })

    # Also accept explicitly written arrow flows; no relationship is created from
    # component co-occurrence alone.
    for chunk in chunks:
        for line in chunk.get("content", "").splitlines():
            if "->" not in line and "→" not in line:
                continue
            names = COMPONENT_REFERENCE.findall(line)
            for source, target in zip(names, names[1:]):
                edges.append({
                    "source": source,
                    "target": target,
                    "interface_name": UNSUPPORTED,
                    "evidence_type": "explicit documented flow arrow",
                    "citations": [_citation(chunk, line.strip())],
                })
    unique_edges = {}
    for edge in edges:
        key = (edge["source"], edge["target"])
        previous = unique_edges.get(key)
        if previous is None:
            unique_edges[key] = edge
            continue
        citations = previous["citations"] + edge["citations"]
        preferred = edge if edge["interface_name"] != UNSUPPORTED else previous
        preferred["citations"] = list({
            (item.get("document_id"), item.get("version"), item.get("chunk_id")): item
            for item in citations
        }.values())
        if previous["evidence_type"] != edge["evidence_type"]:
            preferred["evidence_type"] = "explicit flow and matched documented interface"
        unique_edges[key] = preferred
    return matrix, list(unique_edges.values())


def _finding(
    category: str,
    kind: str,
    title: str,
    rationale: str,
    evidence: str,
    citations: List[Dict[str, Any]],
    severity: str = "MEDIUM",
) -> Dict[str, Any]:
    seed = f"{category}|{title}|{evidence}"
    return {
        "finding_id": hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16],
        "category": category,
        "classification": kind,
        "title": title,
        "severity": severity,
        "severity_rationale": rationale,
        "evidence": evidence,
        "citations": list({c["chunk_id"]: c for c in citations}.values()),
        "engineering_review_status": "PENDING_ENGINEERING_REVIEW",
        "review_note": None,
    }


def _inconsistencies(
    matrix: List[Dict[str, Any]], dependencies: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    findings = []
    for row in matrix:
        if row["target_component"] == UNSUPPORTED:
            continue
        label = f"{row['source_component']} -> {row['target_component']} ({row['interface_name']})"
        if row["data_type"] != UNSUPPORTED and row["input_port"] != UNSUPPORTED:
            input_type = row["input_data_type"]
            if input_type != UNSUPPORTED and input_type != row["data_type"]:
                findings.append(_finding(
                    "signal_data_type", "explicit_contradiction",
                    f"Data type disagreement on {label}",
                    "Different explicitly documented sender and receiver types can cause incompatible interpretation; verify the interface contract.",
                    f"Output type: {row['data_type']}; input type: {input_type}.",
                    row["citations"], "HIGH",
                ))
        if (
            row["protocol"] != UNSUPPORTED
            and row["target_protocol"] != UNSUPPORTED
            and row["protocol"] != row["target_protocol"]
        ):
            findings.append(_finding(
                "interface", "explicit_contradiction",
                f"Protocol disagreement on {label}",
                "The sender and receiver document different communication protocols or media for the same interface; verify the interface contract.",
                f"Output protocol: {row['protocol']}; input protocol: {row['target_protocol']}.",
                row["citations"], "HIGH",
            ))
        output_ms = _period_ms(row["transmission_period"])
        expected_ms = _period_ms(row["expected_period"])
        if output_ms is not None and expected_ms is not None and output_ms != expected_ms:
            findings.append(_finding(
                "timing", "explicit_contradiction",
                f"Transmission timing conflicts with receiver expectation on {label}",
                "The documented sender period differs from the receiver's stated requirement, which may affect data freshness or control-loop behavior.",
                f"Sender transmission period: {row['transmission_period']}; receiver expectation: {row['expected_period']}.",
                row["citations"], "HIGH",
            ))

    adjacency: Dict[str, List[str]] = defaultdict(list)
    for edge in dependencies:
        adjacency[edge["source"]].append(edge["target"])
    visiting, visited = set(), set()

    def visit(node: str, path: List[str]) -> None:
        if node in visiting:
            cycle = path[path.index(node):]
            cycle_edges = [
                edge for edge in dependencies
                if edge["source"] in cycle and edge["target"] in cycle
            ]
            citations = [citation for edge in cycle_edges for citation in edge["citations"]]
            findings.append(_finding(
                "dependency", "inferred_concern",
                "Documented dependency cycle: " + " -> ".join(cycle),
                "A cycle in the documented flow may indicate feedback or ordering behavior that needs explicit architectural review.",
                "The cited dependencies form a directed cycle; the source does not establish whether the cycle is intentional.",
                citations,
                "MEDIUM",
            ))
            return
        if node in visited:
            return
        visiting.add(node)
        for neighbor in adjacency.get(node, []):
            visit(neighbor, path + [neighbor])
        visiting.remove(node)
        visited.add(node)

    for node in list(adjacency):
        visit(node, [node])
    return list({item["finding_id"]: item for item in findings}.values())


def analyze_hld(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract HLD structures and potential inconsistencies from indexed source chunks."""
    components, _ = _component_records(chunks)
    matrix, dependencies = _matrix_and_edges(components, chunks)
    findings = _inconsistencies(matrix, dependencies)
    nodes = sorted({component["component_name"] for component in components})
    edges_for_dot = sorted({(edge["source"], edge["target"]) for edge in dependencies})
    graph = "digraph HLD {\n" + "".join(f'  "{src}" -> "{dst}";\n' for src, dst in edges_for_dot) + "}"
    return {
        "components": components,
        "interface_matrix": matrix,
        "dependencies": {"nodes": nodes, "edges": dependencies, "graphviz": graph},
        "inconsistencies": findings,
        "unsupported_information": (
            ["No component definitions were found in the indexed source."]
            if not components else []
        ),
        "disclaimer": (
            "Advisory analysis only. Every finding requires human engineering review; "
            "this report does not approve an architecture or establish ISO compliance or safety certification."
        ),
    }


def _revision_entities(chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    components, _ = _component_records(chunks)
    removed_components = set()
    for chunk in chunks:
        for line in chunk.get("content", "").splitlines():
            if re.search(r"\b(?:removed|deprecated|deleted|retired)\b", line, re.I):
                removed_components.update(COMPONENT_REFERENCE.findall(line))
    entities: Dict[str, Dict[str, Dict[str, Any]]] = {
        "components": {},
        "interfaces": {},
        "signals": {},
        "protocols": {},
        "timing_requirements": {},
    }
    for component in components:
        name = component["component_name"]
        if name in removed_components:
            continue
        component_value = {
            "component_type": component["component_type"],
            "functions": component["functions"],
            "execution_period": component["execution_period"],
        }
        component_value = {
            key: value for key, value in component_value.items()
            if value != UNSUPPORTED and value != [UNSUPPORTED]
        }
        entities["components"][name] = {
            "value": component_value,
            "citations": component["citations"],
        }
        for port in component["ports"]:
            interface_name = port["interface_name"]
            if interface_name != UNSUPPORTED:
                interface_key = f"{name}|{port['direction']}|{interface_name}"
                entry = entities["interfaces"].get(interface_key)
                if entry is None:
                    interface_value = {
                        "component": name,
                        "direction": port["direction"],
                        "interface": interface_name,
                    }
                    if port["port_name"] != UNSUPPORTED:
                        interface_value["port"] = port["port_name"]
                    entities["interfaces"][interface_key] = {
                        "value": interface_value,
                        "citations": port["citations"],
                    }
                else:
                    if port["port_name"] != UNSUPPORTED:
                        ports = entry["value"].setdefault("ports", [])
                        if port["port_name"] not in ports:
                            ports.append(port["port_name"])
                    entry["citations"].extend(port["citations"])
            if port["data_type"] != UNSUPPORTED:
                entities["signals"][f"{name}|{port['port_name']}"] = {
                    "value": {"component": name, "port": port["port_name"], "data_type": port["data_type"]},
                    "citations": port["citations"],
                }
            if port["protocol"] != UNSUPPORTED:
                entities["protocols"][f"{name}|{port['port_name']}"] = {
                    "value": {"component": name, "port": port["port_name"], "protocol": port["protocol"]},
                    "citations": port["citations"],
                }
            timing = port["transmission_period"]
            if timing != UNSUPPORTED:
                timing_key = f"{name}|{interface_name if interface_name != UNSUPPORTED else port['port_name']}|transmission"
                entities["timing_requirements"][timing_key] = {
                    "value": {"component": name, "transmission_period": timing},
                    "citations": port["citations"],
                }

        if component["execution_period"] != UNSUPPORTED:
            entities["timing_requirements"][f"{name}|execution"] = {
                "value": {"component": name, "execution_period": component["execution_period"]},
                "citations": component["citations"],
            }

    # Signals can also be stated explicitly without a port definition.
    for chunk in chunks:
        for line in chunk.get("content", "").splitlines():
            if re.search(r"\b(?:removed|deprecated|deleted|retired)\b", line, re.I):
                continue
            match = re.search(r"\bSignal\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", line, re.I)
            if match:
                name = match.group(1)
                entities["signals"].setdefault(name, {
                    "value": {"signal": name, "statement": line.strip()},
                    "citations": [_citation(chunk, line.strip())],
                })
    return entities


def _explicit_removals(
    chunks: List[Dict[str, Any]],
    before_entities: Dict[str, Dict[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    known_names = set()
    for category in before_entities.values():
        for key, entity in category.items():
            known_names.add(key)
            value = entity["value"]
            for field_value in value.values():
                if isinstance(field_value, str):
                    known_names.add(field_value)
                elif isinstance(field_value, list):
                    known_names.update(item for item in field_value if isinstance(item, str))

    removals = []
    for chunk in chunks:
        for line in chunk.get("content", "").splitlines():
            if not re.search(r"\b(?:removed|deprecated|deleted|retired)\b", line, re.I):
                continue
            names = set(re.findall(
                r"\b(?:SWC|IF)_[A-Za-z0-9_]+\b|\b[A-Za-z_][A-Za-z0-9_]*_t\b",
                line,
            ))
            names.update(name for name in known_names if name and name.lower() in line.lower())
            for name in names:
                removals.append({
                    "name": name,
                    "statement": line.strip(),
                    "citations": [_citation(chunk, line.strip())],
                })
    return removals


def _revision_absence_citation(
    document: Dict[str, Any], category: str, key: str
) -> Dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "document_name": document["filename"],
        "version": document["version_number"],
        "page": None,
        "section": "Indexed revision scope",
        "chunk_id": None,
        "evidence_type": "absence_in_indexed_revision",
        "snippet": (
            f"Compared the indexed contents of {document['filename']} "
            f"v{document['version_number']}; no matching {category[:-1]} '{key}' was extracted."
        ),
    }


def compare_revisions(
    before_chunks: List[Dict[str, Any]],
    after_chunks: List[Dict[str, Any]],
    before_document: Dict[str, Any],
    after_document: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two actual indexed document versions; absence is not inferred as evidence."""
    before_entities = _revision_entities(before_chunks)
    after_entities = _revision_entities(after_chunks)
    changes = []
    explicit_removals = _explicit_removals(after_chunks, before_entities)
    for category in before_entities:
        before_map, after_map = before_entities[category], after_entities[category]
        for key in sorted(set(before_map) | set(after_map)):
            old, new = before_map.get(key), after_map.get(key)
            if old is None and new is not None:
                changes.append(_revision_change(
                    category, "added", key, None, new, before_document,
                    after_document,
                ))
                continue
            if new is None and old is not None:
                # An omitted section is not proof of a deletion. Require an explicit
                # removal statement naming the documented item in the later revision.
                matched_removal = next(
                    (item for item in explicit_removals
                     if item["name"] in key or item["name"] in json.dumps(old["value"])),
                    None,
                )
                if matched_removal:
                    change = _revision_change(
                        category, "removed", key, old, None,
                        before_document, after_document,
                    )
                    change["citations"].append(matched_removal["citations"][0])
                    change["explicit_removal_statement"] = matched_removal["statement"]
                    changes.append(change)
                continue
            if old is None or new is None:
                continue
            shared_keys = set(old["value"]) & set(new["value"])
            if not shared_keys:
                continue
            before_shared = {field: old["value"][field] for field in shared_keys}
            after_shared = {field: new["value"][field] for field in shared_keys}
            if before_shared == after_shared:
                continue
            changes.append(_revision_change(
                category, "modified", key, old, new,
                before_document, after_document,
                before_value=before_shared, after_value=after_shared,
            ))

    known_signal_names = set(before_entities["signals"]) | set(after_entities["signals"])
    for removal in explicit_removals:
        if removal["name"] not in known_signal_names and removal["name"].endswith("_t"):
            changes.append({
                "change_id": hashlib.sha1(
                    f"signals|{removal['name']}|removed".encode()
                ).hexdigest()[:16],
                "category": "signals",
                "change_type": "removed",
                "entity": removal["name"],
                "before": None,
                "after": None,
                "citations": [
                    _revision_absence_citation(before_document, "signals", removal["name"]),
                    removal["citations"][0],
                ],
                "explicit_removal_statement": removal["statement"],
                "engineering_review_status": "PENDING_ENGINEERING_REVIEW",
                "review_note": None,
            })
    return {
        "before_revision": before_document,
        "after_revision": after_document,
        "changes": changes,
        "disclaimer": (
            "Advisory comparison of two indexed document revisions only. Review all changes against the source documents; "
            "this comparison does not approve an architecture or establish ISO compliance or safety certification."
        ),
    }


def _revision_change(
    category: str,
    change_type: str,
    key: str,
    old: Optional[Dict[str, Any]],
    new: Optional[Dict[str, Any]],
    before_document: Dict[str, Any],
    after_document: Dict[str, Any],
    before_value: Any = None,
    after_value: Any = None,
) -> Dict[str, Any]:
    citations = [
        *(old["citations"] if old else []),
        *(new["citations"] if new else []),
    ]
    if old is None:
        citations.append(_revision_absence_citation(before_document, category, key))
    if new is None:
        citations.append(_revision_absence_citation(after_document, category, key))
    return {
        "change_id": hashlib.sha1(f"{category}|{key}|{change_type}".encode()).hexdigest()[:16],
        "category": category,
        "change_type": change_type,
        "entity": key,
        "before": before_value if before_value is not None else (old["value"] if old else None),
        "after": after_value if after_value is not None else (new["value"] if new else None),
        "citations": list({(c.get("document_id"), c.get("version"), c.get("chunk_id"), c.get("snippet")): c for c in citations}.values()),
        "engineering_review_status": "PENDING_ENGINEERING_REVIEW",
        "review_note": None,
    }


def serialize_report(payload: Dict[str, Any], output_format: str) -> Tuple[bytes, str]:
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"), "application/json"
    if output_format != "csv":
        raise ValueError("Unsupported report format; choose json or csv.")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["section", "record_type", "record_id", "summary", "details", "citations"],
    )
    writer.writeheader()
    if "components" in payload:
        for component in payload["components"]:
            writer.writerow({
                "section": "component_inventory",
                "record_type": "component",
                "record_id": component["component_name"],
                "summary": component["component_type"],
                "details": json.dumps({key: component[key] for key in ("functions", "execution_period", "ports")}, ensure_ascii=False),
                "citations": json.dumps(component["citations"], ensure_ascii=False),
            })
        for row in payload.get("interface_matrix", []):
            writer.writerow({
                "section": "interface_matrix", "record_type": "interface",
                "record_id": row["interface_name"],
                "summary": f"{row['source_component']} -> {row['target_component']}",
                "details": json.dumps(row, ensure_ascii=False),
                "citations": json.dumps(row["citations"], ensure_ascii=False),
            })
        for finding in payload.get("inconsistencies", []):
            writer.writerow({
                "section": "inconsistencies", "record_type": finding["category"],
                "record_id": finding["finding_id"], "summary": finding["title"],
                "details": json.dumps(finding, ensure_ascii=False),
                "citations": json.dumps(finding["citations"], ensure_ascii=False),
            })
        for edge in payload.get("dependencies", {}).get("edges", []):
            writer.writerow({
                "section": "dependencies", "record_type": "edge",
                "record_id": f"{edge['source']}->{edge['target']}",
                "summary": edge["interface_name"], "details": json.dumps(edge, ensure_ascii=False),
                "citations": json.dumps(edge["citations"], ensure_ascii=False),
            })
    for change in payload.get("changes", []):
        writer.writerow({
            "section": "revision_comparison", "record_type": change["category"],
            "record_id": change["change_id"],
            "summary": f"{change['change_type']}: {change['entity']}",
            "details": json.dumps({"before": change["before"], "after": change["after"]}, ensure_ascii=False),
            "citations": json.dumps(change["citations"], ensure_ascii=False),
        })
    return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
