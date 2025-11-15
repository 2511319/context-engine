import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { ProjectProvider } from "./context/ProjectContext";
import ConfigPage from "./pages/Config";
import ExplainPage from "./pages/Explain";
import GraphPreviewPage from "./pages/GraphPreview";
import IndexHealthPage from "./pages/IndexHealth";
import JobsPage from "./pages/Jobs";
import LivePlansPage from "./pages/LivePlans";
import QuickToolsPage from "./pages/QuickTools";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#5df2d6" },
    background: { default: "#0f172a", paper: "#1e293b" }
  }
});

function App(): JSX.Element {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ProjectProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<LivePlansPage />} />
            <Route path="/explain" element={<ExplainPage />} />
            <Route path="/graph" element={<GraphPreviewPage />} />
            <Route path="/health" element={<IndexHealthPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/tools" element={<QuickToolsPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Route>
        </Routes>
      </ProjectProvider>
    </ThemeProvider>
  );
}

export default App;
