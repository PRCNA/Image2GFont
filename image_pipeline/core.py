import math
import numpy as np
from scipy import ndimage as ndi


def preprocess(gray, blur=2.0, threshold=22.0, closing=5, min_area=80, background_sigma=80, silhouette_sigma=1.5, max_hole_area=None):
    """Parameters use working-image pixels; foreground is True."""
    smooth = ndi.gaussian_filter(gray.astype(float), blur)
    background = ndi.gaussian_filter(gray.astype(float), background_sigma)
    mask = background - smooth > threshold
    mask = ndi.binary_closing(mask, structure=np.ones((closing, closing)))
    labels, count = ndi.label(mask)
    areas = np.bincount(labels.ravel())
    keep = areas >= min_area
    keep[0] = False
    mask = keep[labels]
    # Legacy mode fills all holes; multi-stroke experiments preserve larger
    # enclosed whitespace (such as the interior of a mouth-shaped component).
    filled = ndi.binary_fill_holes(mask)
    if max_hole_area is None:
        mask = filled
    else:
        holes, _ = ndi.label(filled & ~mask)
        hole_areas = np.bincount(holes.ravel())
        small = hole_areas <= max_hole_area
        small[0] = False
        mask = mask | small[holes]
    mask = ndi.gaussian_filter(mask.astype(float), silhouette_sigma) >= 0.5
    return mask


def skeletonize(mask):
    """Zhang-Suen parallel thinning, with zero padding at image boundaries."""
    a = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p = [a[:-2, 1:-1], a[:-2, 2:], a[1:-1, 2:], a[2:, 2:],
                 a[2:, 1:-1], a[2:, :-2], a[1:-1, :-2], a[:-2, :-2]]
            neighbors = sum(p)
            transitions = sum((p[i] == 0) & (p[(i + 1) % 8] == 1) for i in range(8))
            if step == 0:
                gate = (p[0] * p[2] * p[4] == 0) & (p[2] * p[4] * p[6] == 0)
            else:
                gate = (p[0] * p[2] * p[6] == 0) & (p[0] * p[4] * p[6] == 0)
            center = a[1:-1, 1:-1]
            remove = (center == 1) & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1) & gate
            if remove.any():
                center[remove] = 0
                changed = True
        if not changed:
            return a[1:-1, 1:-1].astype(bool)


def adjacency(skeleton):
    pixels = set(zip(*np.where(skeleton)))
    result = {}
    for y, x in sorted(pixels):
        nearby = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = (y + dy, x + dx)
                if (dy or dx) and q in pixels:
                    # Avoid shortcut triangles around a right-angle corner.
                    if dy and dx and ((y + dy, x) in pixels or (y, x + dx) in pixels):
                        continue
                    nearby.append(q)
        result[(y, x)] = nearby
    return result


def prune_spurs(skeleton, max_length=12):
    result = skeleton.copy()
    removed = 0
    while True:
        adj = adjacency(result)
        discard = set()
        for start in adj:
            if len(adj[start]) != 1:
                continue
            chain = [start]
            previous, current = start, adj[start][0]
            length = math.dist(start, current)
            while len(adj[current]) == 2:
                chain.append(current)
                nxt = next(p for p in adj[current] if p != previous)
                length += math.dist(current, nxt)
                previous, current = current, nxt
            if len(adj[current]) >= 3 and length < max_length:
                discard.update(chain)
        if not discard:
            return result, removed
        for y, x in discard:
            result[y, x] = False
        removed += len(discard)


def graph_from_skeleton(skeleton):
    adj = adjacency(skeleton)
    special = {p for p in adj if len(adj[p]) != 2}
    groups = []
    while special:
        todo = [min(special)]
        special.remove(todo[0])
        group = []
        while todo:
            p = todo.pop()
            group.append(p)
            for q in adj[p]:
                if q in special and len(adj[p]) >= 3 and len(adj[q]) >= 3:
                    special.remove(q)
                    todo.append(q)
        groups.append(sorted(group))
    owner = {p: i for i, group in enumerate(groups) for p in group}
    centers = [[float(np.mean([p[1] for p in g])), float(np.mean([p[0] for p in g]))] for g in groups]
    edges, visited = [], set()

    def mark(a, b):
        visited.add(tuple(sorted((a, b))))

    for start in sorted(owner):
        for nxt in adj[start]:
            if nxt in owner and owner[nxt] == owner[start]:
                mark(start, nxt)
                continue
            if tuple(sorted((start, nxt))) in visited:
                continue
            path = [start, nxt]
            mark(start, nxt)
            while path[-1] not in owner:
                previous, current = path[-2:]
                following = next(p for p in adj[current] if p != previous)
                mark(current, following)
                path.append(following)
            a, b = owner[start], owner[path[-1]]
            points = [centers[a]] + [[float(x), float(y)] for y, x in path[1:-1]] + [centers[b]]
            edges.append(dict(id=len(edges), start=a, end=b, points=points))
    # Closed components contain no endpoints/junctions: preserve each loop.
    for start in sorted(adj):
        for nxt in adj[start]:
            if tuple(sorted((start, nxt))) in visited:
                continue
            path = [start, nxt]
            mark(start, nxt)
            while path[-1] != start:
                previous, current = path[-2:]
                options = [p for p in adj[current] if p != previous]
                if not options:
                    break
                following = options[0]
                mark(current, following)
                path.append(following)
            i = len(centers)
            centers.append([float(start[1]), float(start[0])])
            edges.append(dict(id=len(edges), start=i, end=i,
                              points=[[float(x), float(y)] for y, x in path]))
    degree = [0] * len(centers)
    for e in edges:
        degree[e['start']] += 1
        degree[e['end']] += 1
    # Keep isolated single pixels as separate one-point candidates.
    for i, d in enumerate(degree):
        if d == 0:
            edges.append(dict(id=len(edges), start=i, end=i, points=[centers[i]]))
    nodes = [dict(id=i, point=p, degree=degree[i]) for i, p in enumerate(centers)]
    return dict(nodes=nodes, edges=edges)


def candidate_strokes(graph, min_angle=140):
    """Greedy tangent continuity only; no claim of true handwriting order."""
    edges = graph['edges']
    incident = {}
    for edge in edges:
        for side, node in enumerate((edge['start'], edge['end'])):
            incident.setdefault(node, []).append((edge['id'], side))
    pairs = {}
    for node, ends in incident.items():
        choices = []
        for i, a in enumerate(ends):
            for b in ends[i + 1:]:
                if a[0] == b[0]:
                    continue
                vectors = []
                for idx, side in (a, b):
                    points = edges[idx]['points'][::1 if side == 0 else -1]
                    origin = np.array(points[0])
                    target = points[-1]
                    for p in points[1:]:
                        if np.linalg.norm(np.array(p) - origin) >= 12:
                            target = p
                            break
                    vector = np.array(target) - origin
                    vectors.append(vector / max(np.linalg.norm(vector), 1e-9))
                angle = math.degrees(math.acos(float(np.clip(np.dot(*vectors), -1, 1))))
                if angle >= min_angle:
                    choices.append((-angle, a, b))
        for _, a, b in sorted(choices):
            if a not in pairs and b not in pairs:
                pairs[a], pairs[b] = b, a
    strokes, used = [], set()
    ends = [(e['id'], s) for e in edges for s in (0, 1)]
    for start in sorted(ends, key=lambda e: (e in pairs, e)):
        if start[0] in used:
            continue
        current, points, ids = start, [], []
        while current[0] not in used:
            idx, side = current
            used.add(idx)
            ids.append(idx)
            chain = edges[idx]['points'][::1 if side == 0 else -1]
            points.extend(chain if not points else chain[1:])
            exit_end = (idx, 1 - side)
            if exit_end not in pairs:
                break
            current = pairs[exit_end]
        strokes.append(dict(edge_ids=ids, points=points, status='candidate'))
    return strokes


def simplify(points, tolerance=1.5):
    if len(points) <= 2:
        return points
    a, b = np.array(points[0]), np.array(points[-1])
    delta = b - a
    data = np.array(points)
    if np.dot(delta, delta) == 0:
        distances = np.linalg.norm(data - a, axis=1)
    else:
        t = np.clip(((data - a) @ delta) / np.dot(delta, delta), 0, 1)
        distances = np.linalg.norm(data - (a + t[:, None] * delta), axis=1)
    index = int(np.argmax(distances))
    if distances[index] <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)
