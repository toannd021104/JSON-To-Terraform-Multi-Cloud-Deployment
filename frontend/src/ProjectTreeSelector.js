import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, FolderOpen, Folder, CheckSquare, Square } from 'lucide-react';

export default function EnhancedProjectTreeSelector() {
  const [projectData, setProjectData] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [output, setOutput] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const API_URL = "http://localhost:8000";

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/projects`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();

        const formattedData = data.map((project) => ({
          type: project.type,
          parent: project.parent,
          children: project.children,
        }));

        setProjectData(formattedData);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch projects: ' + err.message);
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const toggleExpand = (parent) => {
    setExpanded((prev) => ({
      ...prev,
      [parent]: !prev[parent],
    }));
  };

  const handleSelect = (id, isParent) => {
    setSelected((prev) => {
      const newSelected = { ...prev };
  
      if (isParent) {
        const projectGroup = projectData.find((item) => item.parent === id);
        if (projectGroup) {
          // Toggle state based on current state
          const newState = !prev[id];
          newSelected[id] = newState;
          
          projectGroup.children.forEach((child) => {
            newSelected[child] = newState;
          });
        }
      } else {
        newSelected[id] = !prev[id];
      }
  
      return newSelected;
    });
  };

  const executeCommand = async (command) => {
    const selectedItems = Object.entries(selected)
      .filter(([_, isSelected]) => isSelected)
      .map(([id]) => {
        const parent = projectData.find(p => p.children.includes(id));
        return parent ? `${parent.parent}/${id}` : null;
      })
      .filter(path => path !== null);
  
    if (selectedItems.length === 0) {
      setOutput("Error: No valid projects selected");
      return;
    }
  
    const payload = {
      command,
      folders: selectedItems
    };
  
    setIsExecuting(true);
    setOutput("Starting command execution...\n");
  
    try {
      const response = await fetch(`${API_URL}/terraform/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
  
      const result = await response.json();
      
      let outputText = "";
      Object.entries(result.results).forEach(([folder, result]) => {
        outputText += `=== ${folder} ===\n`;
        outputText += result.output + "\n\n";
      });
      
      setOutput(prev => prev + outputText + "\nExecution completed!");
    } catch (err) {
      setOutput(prev => prev + `\n[ERROR] ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };
  
  const getTypeColor = (type) => {
    const colors = {
      aws: 'bg-orange-100 text-orange-800 border-orange-200',
      openstack: 'bg-blue-100 text-blue-800 border-blue-200',
      azure: 'bg-purple-100 text-purple-800 border-purple-200',
      gcp: 'bg-green-100 text-green-800 border-green-200',
    };
    return colors[type] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-700 rounded-lg">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
        <div className="bg-gray-800 text-white p-4">
          <h2 className="text-xl font-semibold">Automated Terraform Code Generation Framework</h2>
          <p className="text-gray-300 text-sm">Select projects to deploy</p>
        </div>

        <div className="p-4">
          {projectData.map((projectGroup) => (
            <div key={projectGroup.parent} className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
              <div
                className={`flex items-center p-3 cursor-pointer hover:bg-gray-50 ${
                  expanded[projectGroup.parent] ? 'border-b border-gray-200' : ''
                }`}
                onClick={() => toggleExpand(projectGroup.parent)}
              >
                <span className="mr-2 text-gray-500">
                  {expanded[projectGroup.parent] ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                </span>
                <span
                  className="mr-3 text-gray-700"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelect(projectGroup.parent, true);
                  }}
                >
                  {selected[projectGroup.parent] ? (
                    <CheckSquare size={20} className="text-blue-600" />
                  ) : (
                    <Square size={20} />
                  )}
                </span>
                <span className="mr-2 text-gray-600">
                  {expanded[projectGroup.parent] ? <FolderOpen size={20} /> : <Folder size={20} />}
                </span>
                <span className="font-medium flex-grow">{projectGroup.parent}</span>
                <span
                  className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(
                    projectGroup.type
                  )} border`}
                >
                  {projectGroup.type}
                </span>
              </div>

              {expanded[projectGroup.parent] && (
                <div className="bg-gray-50 p-2">
                  {projectGroup.children.map((child) => (
                    <div key={child} className="flex items-center p-2 pl-10 hover:bg-gray-100 rounded-md ml-2">
                      <span className="mr-3 text-gray-700" onClick={() => handleSelect(child, false)}>
                        {selected[child] ? (
                          <CheckSquare size={18} className="text-blue-600" />
                        ) : (
                          <Square size={18} />
                        )}
                      </span>
                      <span className="text-gray-600">{child}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="bg-gray-50 p-4 border-t border-gray-200">
          <h3 className="text-sm font-semibold mb-2 text-gray-700">Selected Projects:</h3>
          <div className="space-y-1">
            {Object.keys(selected).filter((key) => selected[key]).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {Object.keys(selected)
                  .filter((key) => selected[key])
                  .map((key) => (
                    <div
                      key={key}
                      className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium border border-blue-200"
                    >
                      {key}
                    </div>
                  ))}
              </div>
            ) : (
              <div className="text-gray-500 italic">No projects selected</div>
            )}
          </div>
        </div>

        <div className="p-4 border-t border-gray-200 flex justify-end space-x-4">
          <button
            className={`px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 font-medium shadow-sm ${
              isExecuting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            onClick={() => executeCommand('init')}
            disabled={isExecuting}
          >
            Init
          </button>
          <button
            className={`px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium shadow-sm ${
              isExecuting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            onClick={() => executeCommand('apply -auto-approve')}
            disabled={isExecuting}
          >
            Apply
          </button>
          <button
            className={`px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium shadow-sm ${
              isExecuting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            onClick={() => executeCommand('destroy -auto-approve')}
            disabled={isExecuting}
          >
            Destroy
          </button>
          <button onClick={() => setOutput("")} className="px-3 py-1 bg-gray-200 rounded">
            Clear Output
          </button>
        </div>
        <div className="p-4 bg-gray-100 border-t border-gray-200">
          <h3 className="text-sm font-semibold mb-2 text-gray-700">Output:</h3>
          <pre className="bg-gray-800 text-white p-4 rounded-md text-sm overflow-auto max-h-64">
            {output || "No output yet. Select projects and click a command button."}
          </pre>
        </div>
      </div>
    </div>
  );
}