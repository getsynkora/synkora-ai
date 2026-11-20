"use client";

import { useState } from "react";
import { Upload, Database, FileText, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";

interface DataAnalysisPanelProps {
  agentId?: string;
}

export default function DataAnalysisPanel({ agentId }: DataAnalysisPanelProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<"upload" | "query" | "export">("upload");

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/v1/data-analysis/upload-file", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        alert(`File uploaded successfully! Processed ${result.statistics?.rows || 0} rows`);
      } else {
        throw new Error(result.message || "Upload failed");
      }
    } catch (error) {
      alert(`Upload failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleExportReport = async (format: string) => {
    setIsExporting(true);
    try {
      const response = await fetch("/api/v1/data-analysis/export-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          data: [], 
          format, 
          filename: `report_${Date.now()}` 
        }),
      });

      const result = await response.json();

      if (result.success) {
        alert(`Report exported successfully! Format: ${result.format}`);
        if (result.download_url) {
          window.open(result.download_url, "_blank");
        }
      } else {
        throw new Error(result.message || "Export failed");
      }
    } catch (error) {
      alert(`Export failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Data Analysis</CardTitle>
          <CardDescription>
            Upload files, query data sources, and export reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Tab Navigation */}
            <div className="flex space-x-2 border-b">
              <button
                onClick={() => setActiveTab("upload")}
                className={`px-4 py-2 font-medium ${
                  activeTab === "upload"
                    ? "border-b-2 border-azure text-azure"
                    : "text-ink-mute"
                }`}
              >
                Upload File
              </button>
              <button
                onClick={() => setActiveTab("query")}
                className={`px-4 py-2 font-medium ${
                  activeTab === "query"
                    ? "border-b-2 border-azure text-azure"
                    : "text-ink-mute"
                }`}
              >
                Query Data
              </button>
              <button
                onClick={() => setActiveTab("export")}
                className={`px-4 py-2 font-medium ${
                  activeTab === "export"
                    ? "border-b-2 border-azure text-azure"
                    : "text-ink-mute"
                }`}
              >
                Export Report
              </button>
            </div>

            {/* Upload Tab */}
            {activeTab === "upload" && (
              <div className="border-2 border-dashed border-taupe rounded-lg p-12 text-center">
                <Upload className="mx-auto h-12 w-12 text-ash" />
                <h3 className="mt-2 text-sm font-semibold text-ink">Upload CSV or ZIP file</h3>
                <p className="mt-1 text-sm text-ink-mute">
                  Upload data files for analysis (Max 100MB)
                </p>
                <div className="mt-6">
                  <label htmlFor="file-upload">
                    <Button disabled={isUploading}>
                      {isUploading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 motion-safe:animate-spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <Upload className="mr-2 h-4 w-4" />
                          Select File
                        </>
                      )}
                    </Button>
                  </label>
                  <input
                    id="file-upload"
                    name="file-upload"
                    type="file"
                    accept=".csv,.zip"
                    className="sr-only"
                    onChange={handleFileUpload}
                    disabled={isUploading}
                  />
                </div>
              </div>
            )}

            {/* Query Tab */}
            {activeTab === "query" && (
              <div className="rounded-lg border p-6">
                <div className="flex items-center space-x-4">
                  <Database className="h-10 w-10 text-azure" />
                  <div>
                    <h3 className="text-lg font-semibold">Query Data Sources</h3>
                    <p className="text-sm text-ink-mute">
                      Connect to Datadog, Databricks, Docker logs, or databases
                    </p>
                  </div>
                </div>
                <div className="mt-4">
                  <p className="text-sm text-ink-soft">
                    Configure data sources in the <strong>Data Sources</strong> section, then use
                    the agent to query and analyze your data.
                  </p>
                  <a href="/data-sources">
                    <Button variant="outline" className="mt-4">
                      Manage Data Sources
                    </Button>
                  </a>
                </div>
              </div>
            )}

            {/* Export Tab */}
            {activeTab === "export" && (
              <div className="rounded-lg border p-6">
                <div className="flex items-center space-x-4">
                  <FileText className="h-10 w-10 text-leaf" />
                  <div>
                    <h3 className="text-lg font-semibold">Export Reports</h3>
                    <p className="text-sm text-ink-mute">
                      Export analysis results in multiple formats
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <Button
                    variant="outline"
                    disabled={isExporting}
                    onClick={() => handleExportReport("csv")}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                  <Button
                    variant="outline"
                    disabled={isExporting}
                    onClick={() => handleExportReport("excel")}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export Excel
                  </Button>
                  <Button
                    variant="outline"
                    disabled={isExporting}
                    onClick={() => handleExportReport("json")}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export JSON
                  </Button>
                  <Button
                    variant="outline"
                    disabled={isExporting}
                    onClick={() => handleExportReport("html")}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export HTML
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Available Connectors</CardTitle>
          <CardDescription>Connect to various data sources for analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">Datadog</h4>
              <p className="text-sm text-ink-mute mt-1">
                Fetch metrics and logs from Datadog monitoring platform
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">Databricks</h4>
              <p className="text-sm text-ink-mute mt-1">
                Execute SQL queries on Databricks data lakehouse
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">Docker Logs</h4>
              <p className="text-sm text-ink-mute mt-1">
                Fetch logs from Docker containers for analysis
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">Database Connections</h4>
              <p className="text-sm text-ink-mute mt-1">
                Query PostgreSQL, SQLite, Elasticsearch databases
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">CSV Upload</h4>
              <p className="text-sm text-ink-mute mt-1">
                Upload and analyze CSV files with automatic statistics
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h4 className="font-semibold">ZIP Files</h4>
              <p className="text-sm text-ink-mute mt-1">
                Upload ZIP archives containing multiple CSV files
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
