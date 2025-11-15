declare module "react-force-graph-2d" {
  import { FunctionComponent } from "react";

  type NodeObject = Record<string, unknown> & { id?: string | number };
  type LinkEndpoint = string | number | NodeObject;
  type LinkObject = Record<string, unknown> & { source?: LinkEndpoint; target?: LinkEndpoint };

  interface ForceGraphProps {
    graphData: { nodes: NodeObject[]; links: LinkObject[] };
    nodeAutoColorBy?: string | ((node: NodeObject) => string);
    nodeLabel?: string | ((node: NodeObject) => string);
    linkLabel?: string | ((link: LinkObject) => string);
    linkDirectionalArrowLength?: number;
    cooldownTicks?: number;
    height?: number;
    width?: number;
    onNodeClick?: (node: NodeObject) => void;
  }

  const ForceGraph2D: FunctionComponent<ForceGraphProps>;
  export default ForceGraph2D;
}
