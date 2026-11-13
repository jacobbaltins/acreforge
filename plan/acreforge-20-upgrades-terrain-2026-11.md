# AcreForge: 20 practical upgrades

This list reopens the earlier deprecated candidate bank in response to the current request. It does not supersede the five-phase roadmap or change the Phase 4/5 evidence gates. Existing parcel import, AWS elevation sampling, mapped references, road curves, conceptual earthwork, utility estimates, source status, measurement and print sheets are not counted as new.

## Implemented in this tranche

1. **Milestones:** local add/edit/complete/remove reminders with optional dates, a 50-entry creation limit, and confirmed removal.
2. **Storage health:** approximate project JSON size, save failure messaging, recovery, and a pending/failed-save unload warning.
3. **Backup inspection:** metadata preview and cancellation before replacement, retaining existing version validation.
4. **Phase summary:** counts and unrounded site-object subtotals by conceptual phase, reconciling with the existing estimate.
5. **Contingency sensitivity:** local −20%/current/+20% preview of the contingency rate without changing the saved value.
6. **Assumptions register:** source and limitations for boundary, object costs, contingency, terrain, and utilities.
7. **Planning-summary JSON:** a separate current-scenario aggregate export, explicitly distinct from a project backup.
8. **Public-export preflight:** explain retained identifying data and existing redactions, offer cancellation, and exclude new milestone data.
9. **Terrain/earthwork guards:** suppress estimates when samples are missing, imported extent is unknown, or an applicable footprint is rotated/outside the grid; explain remaining rectangular approximations.
10. **Terrain edit provenance:** mark post-import terrain edits and distinguish original sample ranges from the edited terrain.
11. **Terrain sample CSV:** local export of grid node coordinates, relative heights, validity flags, extent, source and modification status, with a non-survey disclaimer.
12. **Terrain cross-section:** enter local endpoints to sample relative heights along a straight line, with explicit no-data gaps and no extrapolation.
13. **Parcel ring checks:** reject invalid coordinates, duplicates, zero-area or self-intersecting rings on new imports without replacing the existing boundary. The import is bounded to 2,000 vertices per ring and 5,000 overall. This is not a full polygon topology or survey validation; hole containment and intersections between rings are not checked. Saved legacy boundaries are not revalidated.
14. **Site-object search/filter:** case-insensitive name/type search and type/phase/status filters, keyboard selection and map centering, without modifying saved objects.
15. **Scenario deltas:** choose a baseline and compare signed values from snapshots with matching metric version; older or missing values remain unavailable. Privacy is explicitly a spacing proxy.
16. **Utility terrain profile:** sample the long centerline of an explicitly drawn utility corridor rectangle, including rotated objects and unknown samples; no engineering or continuous-grade claim.
17. **Local elevation grid CSV:** import a strictly validated rectangular grid in property-local feet, preserve `NA` nodes as unknown, record unverified source provenance, and replace terrain only after validation and confirmation with terrain undo. The contract is documented in README. This is a scoped grid import, not raw LiDAR support.
18. **User-supplied reference inventory:** import, review, hide, focus, replace, or remove a local GeoJSON building/tree reference layer, distinct from proposed objects and AI detection. Accepts 2D WGS84 points or single-exterior-ring polygons; bounded size and validation apply. Backups retain references and public export removes them.
19. **Multi-select site objects:** scenario-scoped checkbox selection with atomic group move, duplicate and confirmed delete, one-step undo and existing parcel checks. Locked selections are rejected.
20. **Alignment/distribution:** align selected footprint edges or centers and distribute equal gaps across the group, with the same atomic parcel checks and undo.

## Product direction beyond this batch

The 20 upgrades are complete within their stated scopes. The local CSV grid does not implement LAS/LAZ, GeoTIFF, CRS conversion or LiDAR point-cloud processing. A realistic future sequence, each requiring separate scope and approval:

1. **Terrain and parcels:** validate supported import formats and georeferencing against known fixtures; retain uncertainty and explicit provenance. Raw LiDAR needs agreed formats, CRS/vertical datums, ground filtering, resource limits and a decoding strategy.
2. **Existing features:** improve review of user-supplied building/tree references and optional public-map coverage; any image detection needs approved imagery, an inference design, privacy review and independent accuracy evaluation.
3. **Conceptual site editing:** extend road and terrain editing with tested geometry, undo and parcel checks; cut/fill and utilities remain non-engineering estimates until independently validated.
4. **Shared digital-twin services:** separately design authentication, authorization, encrypted storage, data lifecycle, backups, operational support and hosting costs before proposing a backend or large-scale collaborative architecture.

No phase above changes the existing Phase 4/5 evidence gates. Automated verified inventories, production-ready AI detection and survey-grade digital twins are not claimed.

### Designer direction for a later chunk

Explore a local reference-image underlay with explicit placement and scale/georeferencing controls for tracing; reusable drag/drop land assets; improvements to linked 2D plan and 3D views; and camera/presentation exports. These are ideas to assess against existing capabilities, not implemented features or a copy of another product's branding or interface. A shared collaborative canvas needs a separately approved backend, access controls and operational design.
