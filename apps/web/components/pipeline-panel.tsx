"use client";

import "@xyflow/react/dist/style.css";
import { addEdge, Background, Connection, Controls, Edge, MiniMap, Node, ReactFlow, useEdgesState, useNodesState } from "@xyflow/react";
import { ChangeEvent, DragEvent, useCallback, useEffect, useState } from "react";
import { activatePipeline, createPipeline, deletePipeline, exportPipelines, importPipelines, listPipelines, listPipelineTemplates, Pipeline, PipelineConfiguration, PipelineNodeType, PipelineTemplate, updatePipeline } from "@/lib/auth-api";

const stages: Array<{ type: PipelineNodeType; label: string }> = [
  { type: "source", label: "Documents" },
  { type: "chunk", label: "Chunk" },
  { type: "embed", label: "Embed" },
  { type: "retrieve", label: "Retrieve" },
  { type: "rerank", label: "Rerank" },
  { type: "generate", label: "Generate" },
  { type: "evaluate", label: "Evaluate" },
];

const stageColors: Record<PipelineNodeType, { bg: string; border: string }> = {
  source: { bg: "#eff6ff", border: "#93c5fd" },
  chunk: { bg: "#eef2ff", border: "#a5b4fc" },
  embed: { bg: "#fdf2f8", border: "#f9a8d4" },
  retrieve: { bg: "#f5f3ff", border: "#c4b5fd" },
  rerank: { bg: "#fffbeb", border: "#fcd34d" },
  generate: { bg: "#fff1f2", border: "#fda4af" },
  evaluate: { bg: "#ecfdf5", border: "#6ee7b7" },
};

function nodeStyle(stage: PipelineNodeType) {
  const c = stageColors[stage] ?? { bg: "#eef2ff", border: "#c7d2fe" };
  return {
    background: c.bg,
    border: `1.5px solid ${c.border}`,
    borderRadius: 10,
    padding: "10px 14px",
    color: "#14162b",
  };
}

const emptyConfig: PipelineConfiguration = { retrieval_mode: "hybrid", top_k: 5, similarity_threshold: 0.25, rerank: true, chunk_size_words: 350, chunk_overlap_words: 50, generation_model: "qwen2.5:3b", nodes: [], edges: [] };

export function PipelinePanel({ projectId, accessToken }: Readonly<{ projectId: string; accessToken: string }>) {
  const [items, setItems] = useState<Pipeline[]>([]);
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [selected, setSelected] = useState<Pipeline>();
  const [name, setName] = useState("My RAG pipeline");
  const [config, setConfig] = useState(emptyConfig);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const loadConfiguration = useCallback((pipelineName: string, value: PipelineConfiguration, pipeline?: Pipeline) => {
    setSelected(pipeline);
    setName(pipelineName);
    setConfig(value);
    setNodes(value.nodes.map((node) => ({
      id: node.id,
      position: { x: node.x, y: node.y },
      data: { label: node.label, stage: node.type },
      style: nodeStyle(node.type),
    })));
    setEdges(value.edges.map((edge) => ({ ...edge, animated: true })));
    setError("");
    setSaved("");
  }, [setEdges, setNodes]);

  useEffect(() => {
    void Promise.all([listPipelines(accessToken, projectId), listPipelineTemplates(accessToken, projectId)])
      .then(([pipelines, presets]) => {
        setItems(pipelines);
        setTemplates(presets);
        if (!pipelines.length && presets[0]) loadConfiguration(`${presets[0].name} pipeline`, presets[0].configuration);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [accessToken, loadConfiguration, projectId]);

  const onConnect = useCallback((connection: Connection) => setEdges((current) => addEdge({ ...connection, animated: true }, current)), [setEdges]);

  const onDragStart = (event: DragEvent, type: PipelineNodeType) => {
    event.dataTransfer.setData("application/flowraga", type);
    event.dataTransfer.effectAllowed = "move";
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    const type = event.dataTransfer.getData("application/flowraga") as PipelineNodeType;
    if (!type || nodes.some((node) => node.data.stage === type)) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const stage = stages.find((item) => item.type === type);
    setNodes((current) => [
      ...current,
      {
        id: `${type}-${Date.now()}`,
        position: { x: event.clientX - bounds.left - 70, y: event.clientY - bounds.top - 25 },
        data: { label: stage?.label ?? type, stage: type },
        style: nodeStyle(type),
      },
    ]);
  };

  const serialize = (): PipelineConfiguration => ({
    ...config,
    rerank: nodes.some((node) => node.data.stage === "rerank"),
    nodes: nodes.map((node) => ({ id: node.id, type: node.data.stage as PipelineNodeType, label: String(node.data.label), x: node.position.x, y: node.position.y })),
    edges: edges.filter((edge) => edge.source && edge.target).map((edge) => ({ id: edge.id, source: edge.source, target: edge.target })),
  });

  const save = () => {
    setError("");
    setSaved("");
    const input = { name, configuration: serialize() };
    const operation = selected ? updatePipeline(accessToken, projectId, selected.id, input) : createPipeline(accessToken, projectId, input);
    void operation
      .then((item) => {
        setSelected(item);
        setSaved(`Saved version ${item.version}`);
        setItems((current) => [item, ...current.filter((value) => value.id !== item.id)]);
      })
      .catch((reason: Error) => setError(reason.message));
  };

  const download = () => {
    void exportPipelines(accessToken, projectId).then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "flowraga-pipelines.json";
      link.click();
      URL.revokeObjectURL(url);
    });
  };

  const upload = (file?: File) => {
    if (!file) return;
    void file.text().then(JSON.parse).then((data) => importPipelines(accessToken, projectId, data))
      .then((created) => setItems((current) => [...created, ...current]))
      .catch(() => setError("Invalid pipeline export file"));
  };

  return (
    <section className="pipeline-panel">
      <p className="eyebrow">Visual pipeline builder</p>
      <h2>Drag, connect, validate, and run your RAG flow</h2>

      <div className="pipeline-toolbar">
        <select
          aria-label="Template"
          defaultValue=""
          onChange={(event) => {
            const preset = templates.find((item) => item.name === event.target.value);
            if (preset) loadConfiguration(`${preset.name} pipeline`, preset.configuration);
          }}
        >
          <option value="" disabled>Load template</option>
          {templates.map((item) => <option key={item.name}>{item.name}</option>)}
        </select>
        <select
          aria-label="Saved pipeline"
          value={selected?.id ?? ""}
          onChange={(event) => {
            const item = items.find((value) => value.id === event.target.value);
            if (item) loadConfiguration(item.name, item.configuration, item);
          }}
        >
          <option value="">New pipeline</option>
          {items.map((item) => (
            <option key={item.id} value={item.id}>{item.name} &middot; v{item.version}{item.is_active ? " \u00b7 active" : ""}</option>
          ))}
        </select>
        <input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} aria-label="Pipeline name" />
        <button className="primary" onClick={save}>Validate &amp; save</button>
        {selected && (
          <button
            className="quiet-button"
            onClick={() =>
              void activatePipeline(accessToken, projectId, selected.id).then((active) => {
                setSelected(active);
                setItems((current) => current.map((item) => ({ ...item, is_active: item.id === active.id })));
                setSaved("Pipeline activated for Q&A");
              })
            }
          >
            Activate
          </button>
        )}
      </div>

      <div className="pipeline-settings">
        <label>Retrieval
          <select value={config.retrieval_mode} onChange={(event) => setConfig({ ...config, retrieval_mode: event.target.value as PipelineConfiguration["retrieval_mode"] })}>
            <option value="hybrid">Hybrid</option>
            <option value="vector">Vector</option>
            <option value="keyword">Keyword</option>
          </select>
        </label>
        <label>Top K<input type="number" min="1" max="20" value={config.top_k} onChange={(event) => setConfig({ ...config, top_k: Number(event.target.value) })} /></label>
        <label>Threshold<input type="number" min="0" max="1" step="0.05" value={config.similarity_threshold} onChange={(event) => setConfig({ ...config, similarity_threshold: Number(event.target.value) })} /></label>
        <label>Chunk size<input type="number" min="50" max="2000" value={config.chunk_size_words} onChange={(event) => setConfig({ ...config, chunk_size_words: Number(event.target.value) })} /></label>
        <label>Overlap<input type="number" min="0" max="500" value={config.chunk_overlap_words} onChange={(event) => setConfig({ ...config, chunk_overlap_words: Number(event.target.value) })} /></label>
        <label>Model<input value={config.generation_model} onChange={(event) => setConfig({ ...config, generation_model: event.target.value })} /></label>
      </div>

      <div className="pipeline-builder">
        <aside>
          {stages.map((stage) => (
            <button draggable onDragStart={(event) => onDragStart(event, stage.type)} key={stage.type}>{stage.label}</button>
          ))}
          <small>Drag stages onto the canvas, then connect the handles in execution order.</small>
        </aside>
        <div className="pipeline-canvas" onDrop={onDrop} onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }}>
          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} fitView deleteKeyCode={["Backspace", "Delete"]}>
            <MiniMap />
            <Controls />
            <Background />
          </ReactFlow>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}
      {saved && <p className="form-success">{saved}</p>}

      <div className="document-actions">
        <button className="quiet-button" disabled={!items.length} onClick={download}>Export JSON</button>
        <label className="quiet-button">
          Import JSON
          <input hidden type="file" accept="application/json,.json" onChange={(event: ChangeEvent<HTMLInputElement>) => upload(event.target.files?.[0])} />
        </label>
        {selected && (
          <button
            className="quiet-button"
            onClick={() =>
              void deletePipeline(accessToken, projectId, selected.id).then(() => {
                setItems((current) => current.filter((item) => item.id !== selected.id));
                setSelected(undefined);
                setSaved("Pipeline removed");
              })
            }
          >
            Delete
          </button>
        )}
      </div>
    </section>
  );
}
