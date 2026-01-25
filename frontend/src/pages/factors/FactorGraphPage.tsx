import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import CytoscapeComponent from 'react-cytoscapejs';
import { Search, ZoomIn, ZoomOut, Maximize2, Filter } from 'lucide-react';
import { factorsApi } from '../../services/api';
import type { FactorGraph, FactorNode } from '../../types';

const RELATIONSHIP_TYPES = [
  { id: 'derived-from', label: 'Derived From', color: '#3b82f6' },
  { id: 'correlated-with', label: 'Correlated With', color: '#10b981' },
  { id: 'causes', label: 'Causes', color: '#f59e0b' },
  { id: 'leads', label: 'Leads', color: '#8b5cf6' },
  { id: 'component-of', label: 'Component Of', color: '#ef4444' },
];

const DOMAINS = [
  { id: 'travel', label: 'Travel' },
  { id: 'real_estate', label: 'Real Estate' },
  { id: 'energy', label: 'Energy' },
  { id: 'infrastructure', label: 'Infrastructure' },
  { id: 'entertainment', label: 'Entertainment' },
  { id: 'insurance', label: 'Insurance' },
];

const DOMAIN_COLORS: Record<string, string> = {
  travel: '#3b82f6',
  real_estate: '#10b981',
  energy: '#f59e0b',
  infrastructure: '#8b5cf6',
  entertainment: '#ef4444',
  insurance: '#06b6d4',
};

export function FactorGraphPage() {
  const navigate = useNavigate();
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRelationships, setSelectedRelationships] = useState<string[]>(
    RELATIONSHIP_TYPES.map((r) => r.id)
  );
  const [selectedDomains, setSelectedDomains] = useState<string[]>(
    DOMAINS.map((d) => d.id)
  );
  const [selectedNode, setSelectedNode] = useState<FactorNode | null>(null);

  const { data: graphData, isLoading } = useQuery({
    queryKey: ['factor-graph', selectedRelationships, selectedDomains],
    queryFn: () =>
      factorsApi.getFactorGraph({
        relationship_type: selectedRelationships.join(','),
        domain: selectedDomains.join(','),
      }),
  });

  const graph: FactorGraph | undefined = graphData?.data;

  const cytoscapeElements = graph
    ? [
        ...graph.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label,
            domain: node.domain,
            type: node.type,
          },
        })),
        ...graph.edges.map((edge, idx) => ({
          data: {
            id: `edge-${idx}`,
            source: edge.source,
            target: edge.target,
            relationship: edge.relationship,
          },
        })),
      ]
    : [];

  const cytoscapeStylesheet = [
    {
      selector: 'node',
      style: {
        'background-color': (ele: any) =>
          DOMAIN_COLORS[ele.data('domain')] || '#6b7280',
        label: 'data(label)',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'font-size': '10px',
        color: '#374151',
        'text-margin-y': 5,
        width: (ele: any) => (ele.data('type') === 'source' ? 30 : 20),
        height: (ele: any) => (ele.data('type') === 'source' ? 30 : 20),
        shape: (ele: any) => (ele.data('type') === 'source' ? 'diamond' : 'ellipse'),
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': '#1d4ed8',
      },
    },
    {
      selector: 'edge',
      style: {
        'line-color': (ele: any) => {
          const rel = ele.data('relationship');
          return RELATIONSHIP_TYPES.find((r) => r.id === rel)?.color || '#9ca3af';
        },
        'target-arrow-color': (ele: any) => {
          const rel = ele.data('relationship');
          return RELATIONSHIP_TYPES.find((r) => r.id === rel)?.color || '#9ca3af';
        },
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        width: 2,
      },
    },
  ];

  const handleNodeClick = useCallback((event: any) => {
    const nodeData = event.target.data();
    setSelectedNode({
      id: nodeData.id,
      label: nodeData.label,
      domain: nodeData.domain,
      type: nodeData.type,
    });
  }, []);

  const handleZoomIn = () => {
    cyRef.current?.zoom(cyRef.current.zoom() * 1.2);
  };

  const handleZoomOut = () => {
    cyRef.current?.zoom(cyRef.current.zoom() / 1.2);
  };

  const handleFit = () => {
    cyRef.current?.fit();
  };

  const handleSearch = () => {
    if (!cyRef.current || !searchQuery) return;
    const nodes = cyRef.current.nodes().filter((n) =>
      n.data('label').toLowerCase().includes(searchQuery.toLowerCase())
    );
    if (nodes.length > 0) {
      cyRef.current.fit(nodes, 50);
      nodes.select();
    }
  };

  const toggleRelationship = (relId: string) => {
    setSelectedRelationships((prev) =>
      prev.includes(relId) ? prev.filter((r) => r !== relId) : [...prev, relId]
    );
  };

  const toggleDomain = (domainId: string) => {
    setSelectedDomains((prev) =>
      prev.includes(domainId)
        ? prev.filter((d) => d !== domainId)
        : [...prev, domainId]
    );
  };

  return (
    <div className="h-[calc(100vh-10rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Factor Taxonomy Graph</h1>
          <p className="text-gray-500">
            Explore relationships between factors and data sources
          </p>
        </div>

        {/* Search */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search factors..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="input pl-9 w-64"
            />
          </div>
          <button onClick={handleSearch} className="btn-primary">
            Search
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4">
        {/* Filters Sidebar */}
        <aside className="w-64 flex-shrink-0 space-y-4">
          {/* Zoom Controls */}
          <div className="card p-3 flex items-center justify-center gap-2">
            <button
              onClick={handleZoomIn}
              className="p-2 rounded hover:bg-gray-100"
              title="Zoom In"
            >
              <ZoomIn className="h-5 w-5 text-gray-600" />
            </button>
            <button
              onClick={handleZoomOut}
              className="p-2 rounded hover:bg-gray-100"
              title="Zoom Out"
            >
              <ZoomOut className="h-5 w-5 text-gray-600" />
            </button>
            <button
              onClick={handleFit}
              className="p-2 rounded hover:bg-gray-100"
              title="Fit to Screen"
            >
              <Maximize2 className="h-5 w-5 text-gray-600" />
            </button>
          </div>

          {/* Relationship Types Filter */}
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Edge Types
            </h3>
            <div className="space-y-2">
              {RELATIONSHIP_TYPES.map((rel) => (
                <label key={rel.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedRelationships.includes(rel.id)}
                    onChange={() => toggleRelationship(rel.id)}
                    className="rounded border-gray-300"
                  />
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: rel.color }}
                  />
                  <span className="text-sm text-gray-600">{rel.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Domain Filter */}
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Domains</h3>
            <div className="space-y-2">
              {DOMAINS.map((domain) => (
                <label key={domain.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedDomains.includes(domain.id)}
                    onChange={() => toggleDomain(domain.id)}
                    className="rounded border-gray-300"
                  />
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: DOMAIN_COLORS[domain.id] }}
                  />
                  <span className="text-sm text-gray-600">{domain.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="card p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Legend</h3>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-gray-400" />
                <span>Factor</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rotate-45 bg-gray-400" />
                <span>Data Source</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Graph Canvas */}
        <div className="flex-1 card overflow-hidden relative">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            </div>
          ) : (
            <CytoscapeComponent
              elements={cytoscapeElements}
              stylesheet={cytoscapeStylesheet as any}
              layout={{ name: 'cose', animate: false }}
              cy={(cy) => {
                cyRef.current = cy;
                cy.on('tap', 'node', handleNodeClick);
              }}
              style={{ width: '100%', height: '100%' }}
            />
          )}

          {/* Selected Node Panel */}
          {selectedNode && (
            <div className="absolute bottom-4 left-4 card p-4 w-72 shadow-lg">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h4 className="font-semibold text-gray-900">{selectedNode.label}</h4>
                  <span className="text-xs text-gray-500 capitalize">
                    {selectedNode.type} • {selectedNode.domain.replace('_', ' ')}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
              <button
                onClick={() => navigate(`/factors/${selectedNode.id}`)}
                className="btn-primary w-full mt-2"
              >
                View Details
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
