import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import { useProject } from "../context/ProjectContext";

type GraphResponse = {
  nodes: { id: string; label: string; props: { name?: string; path?: string; doc_name?: string } }[];
  edges: { source: string; target: string; rel_type: string }[];
};

type GraphStats = {
  nodes: Record<string, number>;
  relations: Record<string, number>;
};

type ForceNode = {
  id: string;
  name: string;
  group: string;
  raw: GraphResponse["nodes"][number];
  x?: number;
  y?: number;
};

type ForceLink = {
  source: string | ForceNode;
  target: string | ForceNode;
  rel_type: string;
};

const DEFAULT_RELATIONS = ["IMPLEMENTS", "DESCRIBED_IN", "REFERENCES", "APPLIES_TO"];
const COLOR_PALETTE = ["#4dabf5", "#ce93d8", "#ffb74d", "#81c784", "#f48fb1", "#64b5f6", "#a1887f", "#90a4ae"];

const dataURItoBlob = (dataURI: string): Blob => {
  const byteString = atob(dataURI.split(",")[1] ?? "");
  const mimeString = dataURI.split(",")[0]?.split(":")[1]?.split(";")[0] ?? "image/png";
  const buffer = new ArrayBuffer(byteString.length);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < byteString.length; i += 1) {
    view[i] = byteString.charCodeAt(i);
  }
  return new Blob([buffer], { type: mimeString });
};

function GraphPreviewPage(): JSX.Element {
  const { project } = useProject();
  const [moduleName, setModuleName] = useState("");
  const [depth, setDepth] = useState(3);
  const [relations, setRelations] = useState<string[]>(DEFAULT_RELATIONS);
  const [hoverNode, setHoverNode] = useState<ForceNode | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const graphContainerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<ForceGraphMethods<ForceNode, ForceLink>>();
  const [canvasEl, setCanvasEl] = useState<HTMLCanvasElement | null>(null);

  const { data: stats } = useQuery({
    queryKey: ["graph-stats", project],
    queryFn: async () => await apiGet<GraphStats>(`/graph/stats?project=${encodeURIComponent(project)}`)
  });

  const {
    data: graph,
    isFetching,
    refetch,
    error
  } = useQuery({
    queryKey: ["graph", project, moduleName, depth, relations],
    queryFn: async () => {
      const relQuery = relations.map((r) => `relations=${encodeURIComponent(r)}`).join("&");
      const url = `/graph?project=${encodeURIComponent(project)}&module=${encodeURIComponent(moduleName)}&depth=${depth}&${relQuery}`;
      return await apiGet<GraphResponse>(url);
    },
    enabled: false,
    retry: false
  });

  useEffect(() => {
    if (!graphContainerRef.current) return;
    const canvas = graphContainerRef.current.querySelector("canvas");
    if (canvas instanceof HTMLCanvasElement) {
      setCanvasEl(canvas);
    }
  }, [graph]);

  useEffect(() => {
    setModuleName("");
    setHoverNode(null);
    setRelations(DEFAULT_RELATIONS);
  }, [project]);

  const groupColorMap = useMemo(() => {
    const map = new Map<string, string>();
    let idx = 0;
    (graph?.nodes ?? []).forEach((node) => {
      if (!map.has(node.label)) {
        map.set(node.label, COLOR_PALETTE[idx % COLOR_PALETTE.length]);
        idx += 1;
      }
    });
    return map;
  }, [graph]);

  const colorForGroup = useCallback(
    (group?: string) => {
      if (!group) return "#90caf9";
      return groupColorMap.get(group) ?? "#90caf9";
    },
    [groupColorMap]
  );

  const graphData = useMemo<{ nodes: ForceNode[]; links: ForceLink[] }>(() => {
    if (!graph) return { nodes: [], links: [] };
    return {
      nodes: graph.nodes.map((n) => ({
        id: n.id,
        name: n.props?.name || n.props?.path || n.props?.doc_name || n.id,
        group: n.label,
        raw: n
      })),
      links: graph.edges.map((e) => ({
        source: e.source,
        target: e.target,
        rel_type: e.rel_type
      }))
    };
  }, [graph]);

  const toggleRelation = (rel: string): void => {
    setRelations((prev) => (prev.includes(rel) ? prev.filter((r) => r !== rel) : [...prev, rel]));
  };

  const relationOptions = Object.keys(stats?.relations ?? {}).length
    ? Object.keys(stats?.relations ?? {})
    : DEFAULT_RELATIONS;

  const downloadBlob = (filename: string, blob: Blob): void => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportPng = useCallback(() => {
    if (!canvasEl) {
      setExportError("Сначала загрузите граф — canvas ещё не готов.");
      return;
    }
    setExportError(null);
    const dataUrl = canvasEl.toDataURL("image/png");
    downloadBlob(`graph-preview-${moduleName || "context"}.png`, dataURItoBlob(dataUrl));
  }, [canvasEl, moduleName]);

  const handleExportSvg = useCallback(() => {
    const methods = graphRef.current;
    if (!methods) {
      setExportError("Граф ещё не инициализирован.");
      return;
    }
    const bbox = methods.getGraphBbox();
    if (!bbox) {
      setExportError("Не удалось вычислить границы графа.");
      return;
    }
    const nodes = methods.graphData().nodes as ForceNode[];
    const links = methods.graphData().links as ForceLink[];
    if (!nodes.length) {
      setExportError("Граф пуст — экспорт невозможен.");
      return;
    }
    const svgWidth = 1200;
    const svgHeight = 800;
    const padding = 40;
    const width = Math.max(bbox.x[1] - bbox.x[0], 1);
    const height = Math.max(bbox.y[1] - bbox.y[0], 1);
    const scale = Math.min((svgWidth - padding * 2) / width, (svgHeight - padding * 2) / height);

    const projectPoint = (node: ForceNode) => {
      const x = ((node.x ?? 0) - bbox.x[0]) * scale + padding;
      const y = ((node.y ?? 0) - bbox.y[0]) * scale + padding;
      return { x, y };
    };

    const linkLines = links
      .map((link) => {
        const src = (link.source as ForceNode) ?? nodes.find((n) => n.id === link.source);
        const dst = (link.target as ForceNode) ?? nodes.find((n) => n.id === link.target);
        if (!src || !dst || src.x == null || dst.x == null) return "";
        const p1 = projectPoint(src);
        const p2 = projectPoint(dst);
        return `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="#90a4ae" stroke-width="1.5" stroke-linecap="round" />`;
      })
      .join("");

    const nodeCircles = nodes
      .map((node) => {
        if (node.x == null || node.y == null) return "";
        const p = projectPoint(node);
        const color = colorForGroup(node.group);
        return `<g><circle cx="${p.x}" cy="${p.y}" r="6" fill="${color}" /><text x="${p.x + 8}" y="${p.y - 8}" font-size="10" fill="#37474f">${node.name}</text></g>`;
      })
      .join("");

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">${linkLines}${nodeCircles}</svg>`;
    const blob = new Blob([svg], { type: "image/svg+xml" });
    setExportError(null);
    downloadBlob(`graph-preview-${moduleName || "context"}.svg`, blob);
  }, [colorForGroup, moduleName]);

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Graph Preview</Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <TextField
          label="Module"
          fullWidth
          value={moduleName}
          onChange={(e) => setModuleName(e.target.value)}
        />
        <TextField
          label="Depth"
          type="number"
          sx={{ width: 120 }}
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
        />
        <Button
          variant="contained"
          onClick={() => refetch()}
          disabled={!moduleName || isFetching}
        >
          {isFetching ? "Loading..." : "Load Graph"}
        </Button>
      </Stack>

      <Stack direction="row" spacing={1} flexWrap="wrap">
        {relationOptions.map((rel) => (
          <Chip
            key={rel}
            label={`${rel} (${stats?.relations?.[rel] ?? 0})`}
            color={relations.includes(rel) ? "primary" : "default"}
            onClick={() => toggleRelation(rel)}
          />
        ))}
      </Stack>

      {error && <Alert severity="error">{(error as Error).message}</Alert>}
      {exportError && <Alert severity="warning">{exportError}</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1">Node Types</Typography>
              <Stack spacing={1} mt={2}>
                {Object.entries(stats?.nodes ?? {}).map(([label, count]) => (
                  <Box key={label} display="flex" justifyContent="space-between">
                    <Typography>{label}</Typography>
                    <Typography color="text.secondary">{count}</Typography>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={8}>
          <Card sx={{ height: 500 }}>
            <CardContent sx={{ height: "100%", position: "relative" }}>
              <Stack direction="row" spacing={1} mb={2}>
                <ButtonGroup variant="outlined" size="small">
                  <Button onClick={handleExportPng} disabled={!graph}>
                    Экспорт PNG
                  </Button>
                  <Button onClick={handleExportSvg} disabled={!graph}>
                    Экспорт SVG
                  </Button>
                </ButtonGroup>
              </Stack>
              {isFetching && <CircularProgress />}
              <Box ref={graphContainerRef} sx={{ height: 420, position: "relative" }}>
                {graph && (
                  <ForceGraph2D
                    ref={graphRef}
                    graphData={graphData}
                    nodeColor={(node: ForceNode) => colorForGroup(node.group)}
                    nodeLabel={(node: ForceNode) => node.name}
                    linkLabel={(link: ForceLink) => link.rel_type}
                    linkDirectionalArrowLength={4}
                    cooldownTicks={100}
                    onNodeHover={(node?: ForceNode) => setHoverNode(node ?? null)}
                    enableNodeDrag
                    height={420}
                  />
                )}
                {hoverNode && (
                  <Card
                    sx={{
                      position: "absolute",
                      top: 16,
                      right: 16,
                      width: 280,
                      pointerEvents: "none",
                      bgcolor: "rgba(0, 0, 0, 0.7)",
                      color: "common.white"
                    }}
                  >
                    <CardContent>
                      <Typography variant="subtitle2" gutterBottom>
                        {hoverNode.name}
                      </Typography>
                      <Typography variant="body2">Label: {hoverNode.group}</Typography>
                      {hoverNode.raw.props?.path && (
                        <Typography variant="body2">Path: {hoverNode.raw.props.path}</Typography>
                      )}
                      {hoverNode.raw.props?.doc_name && (
                        <Typography variant="body2">Doc: {hoverNode.raw.props.doc_name}</Typography>
                      )}
                    </CardContent>
                  </Card>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  );
}

export default GraphPreviewPage;
