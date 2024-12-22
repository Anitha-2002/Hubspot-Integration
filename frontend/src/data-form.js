import {useState} from "react";
import {Box, Button} from "@mui/material";
import axios from "axios";

const endpointMapping = {
  Notion: "notion",
  Airtable: "airtable",
  Hubspot: "hubspot",
};

export const DataForm = ({integrationType, credentials}) => {
  const [loadedData, setLoadedData] = useState([]);
  const endpoint = endpointMapping[integrationType];

  const handleLoad = async () => {
    try {
      const formData = new FormData();
      formData.append("credentials", JSON.stringify(credentials));
      const response =
        endpoint === "hubspot"
          ? await axios.post(
              `http://localhost:8000/integrations/${endpoint}/get_hubspot_items`,
              formData
            )
          : await axios.post(
              `http://localhost:8000/integrations/${endpoint}/load`,
              formData
            );
      const data = response.data;
      console.log(data);
      setLoadedData(data ?? "no data");
    } catch (e) {
      alert(e?.response?.data?.detail);
    }
  };

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      flexDirection="column"
      width="100%"
    >
      <Box display="flex" flexDirection="column" width="100%">
        <h1>{endpoint} Items</h1>
        {endpoint === "hubspot" && loadedData.length > 0 ? (
          <ul>
            {loadedData.map((item) => (
              <li key={item.id}>
                <p>
                  <strong>Name:</strong> {item.name || "Unnamed"}
                </p>
                <p>
                  <strong>Created At:</strong> {item.creation_time || "N/A"}
                </p>
                <p>
                  <strong>Last Modified:</strong>{" "}
                  {item.last_modified_time || "N/A"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p>No items found.</p>
        )}
        <Button onClick={handleLoad} sx={{mt: 2}} variant="contained">
          Load Data
        </Button>
        <Button
          onClick={() => setLoadedData([])}
          sx={{mt: 1}}
          variant="contained"
        >
          Clear Data
        </Button>
      </Box>
    </Box>
  );
};
