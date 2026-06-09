import { GraphPreview } from "../graph/GraphPreview";
import basicGraph from "../graph/fixtures/basic-graph.json";

// The fixture is typed as `unknown` (import of a JSON file). `GraphPreview`
// routes it through `validateGraph` at render time, so no compile-time type
// assertion is needed and no assumption about fixture shape is baked in here.
const GraphRoute = () => {
  return <GraphPreview graph={basicGraph} />;
};

export default GraphRoute;
