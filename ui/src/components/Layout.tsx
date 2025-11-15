import { AppBar, Box, Button, Container, TextField, Toolbar, Typography } from "@mui/material";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useProject } from "../context/ProjectContext";

const navItems = [
  { label: "Live Plans", path: "/" },
  { label: "Explain", path: "/explain" },
  { label: "Graph", path: "/graph" },
  { label: "Health", path: "/health" },
  { label: "Jobs", path: "/jobs" },
  { label: "Quick Tools", path: "/tools" },
  { label: "Config", path: "/config" }
];

function Layout(): JSX.Element {
  const location = useLocation();
  const { project, setProject } = useProject();

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="static" color="transparent" elevation={1}>
        <Toolbar sx={{ flexWrap: "wrap", gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 0 }}>
            Context Engine UI
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, flexGrow: 1 }}>
            {navItems.map((item) => (
              <Button
                key={item.path}
                component={Link}
                to={item.path}
                color={location.pathname === item.path ? "primary" : "inherit"}
                sx={{ textTransform: "none" }}
              >
                {item.label}
              </Button>
            ))}
          </Box>
          <TextField
            label="Project"
            size="small"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            sx={{ minWidth: 160 }}
            inputProps={{ "aria-label": "Project name" }}
          />
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Outlet />
      </Container>
    </Box>
  );
}

export default Layout;
