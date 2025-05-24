"""
Dependency Resolution System for KOS Package Manager (KPM)

This module provides advanced dependency resolution capabilities for KOS packages,
including version compatibility checking, conflict detection, and optimal installation ordering.
"""

import os
import logging
import json
from typing import Dict, List, Set, Tuple, Optional, Any
import networkx as nx
from packaging import version

from .manager import Package, PackageDependency

logger = logging.getLogger('KOS.package.dependency_resolver')

class DependencyNode:
    """Represents a package node in the dependency graph"""
    def __init__(self, name: str, version: str = None):
        self.name = name
        self.version = version
        self.dependencies = []  # List of DependencyEdge
    
    def __str__(self):
        return f"{self.name}" + (f"-{self.version}" if self.version else "")
    
    def __eq__(self, other):
        if not isinstance(other, DependencyNode):
            return False
        return self.name == other.name
    
    def __hash__(self):
        return hash(self.name)

class DependencyEdge:
    """Represents a dependency relationship between packages"""
    def __init__(self, source: DependencyNode, target: DependencyNode, 
                 required_version: str = None, optional: bool = False):
        self.source = source
        self.target = target
        self.required_version = required_version  # Version constraint (e.g., '>=1.0.0')
        self.optional = optional  # Whether this dependency is optional
    
    def __str__(self):
        constraint = f" {self.required_version}" if self.required_version else ""
        optional = " (optional)" if self.optional else ""
        return f"{self.source} -> {self.target}{constraint}{optional}"

class DependencyGraph:
    """Graph representation of package dependencies"""
    def __init__(self):
        self.nodes = {}  # name -> DependencyNode
        self.graph = nx.DiGraph()
    
    def add_node(self, name: str, version: str = None) -> DependencyNode:
        """Add a package node to the graph"""
        if name not in self.nodes:
            node = DependencyNode(name, version)
            self.nodes[name] = node
            self.graph.add_node(name, version=version)
        else:
            # Update version if provided
            if version and not self.nodes[name].version:
                self.nodes[name].version = version
                self.graph.nodes[name]['version'] = version
        return self.nodes[name]
    
    def add_edge(self, source_name: str, target_name: str, 
                 required_version: str = None, optional: bool = False):
        """Add a dependency edge between packages"""
        source = self.add_node(source_name)
        target = self.add_node(target_name)
        
        edge = DependencyEdge(source, target, required_version, optional)
        source.dependencies.append(edge)
        
        self.graph.add_edge(source_name, target_name, 
                            required_version=required_version, 
                            optional=optional)
    
    def resolve_ordering(self) -> List[str]:
        """Determine the order in which packages should be installed"""
        try:
            # Use topological sort to get installation order
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # Detect cycles in the graph
            cycles = list(nx.simple_cycles(self.graph))
            logger.error(f"Circular dependencies detected: {cycles}")
            
            # Try to break cycles by removing optional dependencies
            for cycle in cycles:
                for i in range(len(cycle)):
                    source = cycle[i]
                    target = cycle[(i + 1) % len(cycle)]
                    if self.graph.has_edge(source, target) and self.graph[source][target].get('optional', False):
                        self.graph.remove_edge(source, target)
                        logger.info(f"Breaking cycle by removing optional dependency: {source} -> {target}")
            
            try:
                return list(nx.topological_sort(self.graph))
            except nx.NetworkXUnfeasible:
                # If we still have cycles, return nodes sorted by their out-degree
                # (nodes with fewer dependencies first)
                return sorted(self.graph.nodes(), key=lambda n: self.graph.out_degree(n))
    
    def check_version_conflicts(self) -> List[Tuple[str, List[Tuple[str, str, str]]]]:
        """
        Check for version conflicts in the dependency graph
        
        Returns:
            List of (package_name, [(requiring_package, required_version, conflict_description)])
        """
        conflicts = []
        
        for node_name, node in self.nodes.items():
            # Find all incoming edges (packages requiring this one)
            requirements = []
            for source, target, data in self.graph.in_edges(node_name, data=True):
                if data.get('required_version'):
                    requirements.append((source, data['required_version']))
            
            if len(requirements) <= 1:
                continue
            
            # Check for conflicting version requirements
            conflict_sets = []
            for i, (req1_pkg, req1_ver) in enumerate(requirements):
                for req2_pkg, req2_ver in requirements[i+1:]:
                    if not self._is_version_compatible(req1_ver, req2_ver):
                        conflict_sets.append((
                            req1_pkg, req1_ver, 
                            req2_pkg, req2_ver,
                            f"Incompatible requirements: {req1_ver} vs {req2_ver}"
                        ))
            
            if conflict_sets:
                formatted_conflicts = [
                    (req1_pkg, req1_ver, desc) for req1_pkg, req1_ver, _, _, desc in conflict_sets
                ] + [
                    (req2_pkg, req2_ver, desc) for _, _, req2_pkg, req2_ver, desc in conflict_sets
                ]
                conflicts.append((node_name, formatted_conflicts))
        
        return conflicts
    
    def _is_version_compatible(self, req1: str, req2: str) -> bool:
        """
        Check if two version requirements are compatible
        
        This is a simplified check that only handles basic version specifiers.
        A more robust implementation would use the packaging library.
        """
        # Parse version requirements
        ops = ['==', '>=', '<=', '>', '<', '!=']
        req1_op = next((op for op in ops if req1.startswith(op)), '')
        req2_op = next((op for op in ops if req2.startswith(op)), '')
        
        if req1_op == '' or req2_op == '':
            return True  # Can't determine conflict with missing operators
        
        req1_ver = req1[len(req1_op):].strip()
        req2_ver = req2[len(req2_op):].strip()
        
        # Check for direct equality conflicts
        if req1_op == '==' and req2_op == '==':
            return req1_ver == req2_ver
        
        # Simple check for range conflicts
        try:
            v1 = version.parse(req1_ver)
            v2 = version.parse(req2_ver)
            
            # Check for basic conflicts
            if req1_op == '>=' and req2_op == '<=' and v1 > v2:
                return False
            if req1_op == '<=' and req2_op == '>=' and v1 < v2:
                return False
            if req1_op == '>' and req2_op == '<' and v1 >= v2:
                return False
            if req1_op == '<' and req2_op == '>' and v1 <= v2:
                return False
            
            # More complex conflicts would need more sophisticated checking
            
            return True
        except Exception:
            # If we can't parse versions, assume compatible
            return True
    
    def visualize(self, output_file: str = 'dependency_graph.png'):
        """Generate a visualization of the dependency graph"""
        try:
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(12, 8))
            pos = nx.spring_layout(self.graph)
            
            # Draw nodes
            nx.draw_networkx_nodes(self.graph, pos, node_size=700, node_color='lightblue')
            
            # Draw edges
            optional_edges = [(u, v) for u, v, d in self.graph.edges(data=True) if d.get('optional')]
            required_edges = [(u, v) for u, v, d in self.graph.edges(data=True) if not d.get('optional')]
            
            nx.draw_networkx_edges(self.graph, pos, edgelist=required_edges, arrows=True)
            nx.draw_networkx_edges(self.graph, pos, edgelist=optional_edges, 
                                  arrows=True, style='dashed', edge_color='gray')
            
            # Draw labels
            labels = {n: f"{n}\n{d.get('version', '')}" for n, d in self.graph.nodes(data=True)}
            nx.draw_networkx_labels(self.graph, pos, labels=labels)
            
            # Draw edge labels for version requirements
            edge_labels = {(u, v): d.get('required_version', '') 
                          for u, v, d in self.graph.edges(data=True) 
                          if d.get('required_version')}
            nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=8)
            
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(output_file)
            plt.close()
            
            return output_file
        except ImportError:
            logger.warning("Matplotlib not available for dependency visualization")
            return None

class DependencyResolver:
    """Resolves package dependencies and detects conflicts"""
    def __init__(self, package_db=None, repo_manager=None):
        self.package_db = package_db
        self.repo_manager = repo_manager
        self.dependency_cache = {}  # package_name -> resolved_dependencies
    
    def build_dependency_graph(self, packages: List[str], include_installed: bool = True) -> DependencyGraph:
        """
        Build a dependency graph for the given packages
        
        Args:
            packages: List of package names to resolve dependencies for
            include_installed: Whether to include already installed packages
            
        Returns:
            DependencyGraph representing the package dependencies
        """
        graph = DependencyGraph()
        visited = set()
        
        # Process each requested package
        for pkg_name in packages:
            self._process_package_dependencies(pkg_name, graph, visited, include_installed)
        
        return graph
    
    def _process_package_dependencies(self, pkg_name: str, graph: DependencyGraph, 
                                     visited: Set[str], include_installed: bool, 
                                     depth: int = 0, max_depth: int = 20):
        """Recursively process package dependencies"""
        if depth > max_depth:
            logger.warning(f"Max dependency depth reached for {pkg_name}, stopping recursion")
            return
        
        if pkg_name in visited:
            return
        
        visited.add(pkg_name)
        
        # Get package info from repository or database
        pkg_info = None
        if self.repo_manager:
            # Try to find package in repositories
            for repo in self.repo_manager.list_repositories():
                for pkg in repo.packages:
                    if pkg.name == pkg_name:
                        pkg_info = pkg
                        break
                if pkg_info:
                    break
        
        # If package not found in repos, check if it's installed
        if not pkg_info and self.package_db and include_installed:
            pkg_info = self.package_db.get_package(pkg_name)
        
        if not pkg_info:
            logger.warning(f"Package {pkg_name} not found in repositories or database")
            return
        
        # Add package to graph
        graph.add_node(pkg_name, pkg_info.version)
        
        # Process dependencies
        for dep in pkg_info.dependencies:
            # Check if it's a valid dependency
            if not dep.name:
                continue
            
            # Handle optional dependencies
            optional = getattr(dep, 'optional', False)
            
            # Add dependency to graph
            version_req = None
            if hasattr(dep, 'version_req') and dep.version_req:
                version_req = dep.version_req
            elif hasattr(dep, 'version') and dep.version:
                version_req = f">={dep.version}"
            
            graph.add_edge(pkg_name, dep.name, version_req, optional)
            
            # Recursively process dependency's dependencies
            self._process_package_dependencies(dep.name, graph, visited, 
                                              include_installed, depth + 1, max_depth)
    
    def resolve_dependencies(self, packages: List[str], include_installed: bool = True) -> Tuple[List[str], List[str]]:
        """
        Resolve dependencies for the given packages
        
        Args:
            packages: List of package names to resolve dependencies for
            include_installed: Whether to include already installed packages
            
        Returns:
            Tuple of (installation_order, missing_packages)
        """
        graph = self.build_dependency_graph(packages, include_installed)
        
        # Check for version conflicts
        conflicts = graph.check_version_conflicts()
        if conflicts:
            for pkg, conflict_details in conflicts:
                logger.warning(f"Version conflicts for {pkg}:")
                for req_pkg, req_ver, desc in conflict_details:
                    logger.warning(f"  Required by {req_pkg} with {req_ver}: {desc}")
        
        # Get installation order
        order = graph.resolve_ordering()
        
        # Identify missing packages
        missing = []
        if self.package_db:
            for pkg in order:
                if not self.package_db.get_package(pkg):
                    missing.append(pkg)
        
        return order, missing
    
    def generate_report(self, packages: List[str]) -> Dict[str, Any]:
        """
        Generate a detailed dependency report for the given packages
        
        Args:
            packages: List of package names to analyze
            
        Returns:
            Dict containing dependency analysis
        """
        graph = self.build_dependency_graph(packages, include_installed=True)
        order, missing = self.resolve_dependencies(packages)
        conflicts = graph.check_version_conflicts()
        
        # Build dependency tree
        tree = {}
        for pkg in packages:
            tree[pkg] = self._build_dependency_tree(pkg, graph, set())
        
        # Create report
        report = {
            'packages': packages,
            'installation_order': order,
            'missing_packages': missing,
            'version_conflicts': [
                {
                    'package': pkg,
                    'conflicts': [
                        {
                            'requiring_package': req_pkg,
                            'required_version': req_ver,
                            'description': desc
                        } for req_pkg, req_ver, desc in conflict_details
                    ]
                } for pkg, conflict_details in conflicts
            ],
            'dependency_tree': tree,
            'total_dependencies': len(order)
        }
        
        return report
    
    def _build_dependency_tree(self, pkg_name: str, graph: DependencyGraph, 
                              visited: Set[str]) -> Dict[str, Any]:
        """Build a recursive dependency tree structure for a package"""
        if pkg_name in visited:
            return {'name': pkg_name, 'circular': True}
        
        visited.add(pkg_name)
        node = graph.nodes.get(pkg_name)
        
        if not node:
            return {'name': pkg_name, 'not_found': True}
        
        result = {
            'name': pkg_name,
            'version': node.version,
            'dependencies': []
        }
        
        # Add dependencies
        for edge in node.dependencies:
            dep_tree = self._build_dependency_tree(edge.target.name, graph, visited.copy())
            if edge.required_version:
                dep_tree['required_version'] = edge.required_version
            if edge.optional:
                dep_tree['optional'] = True
            result['dependencies'].append(dep_tree)
        
        return result
