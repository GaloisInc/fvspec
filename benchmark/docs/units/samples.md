# Unit Test Samples from fvspec Benchmark

This document contains randomly sampled unit tests from the fvspec benchmark dataset. Each sample includes:

- The sample ID (5-digit PBT identifier)
- The source repository
- A summary of the property-based test (PBT)
- The total count of unit tests associated with that PBT
- Up to 5 representative unit tests

These samples demonstrate the diversity of real-world Python test code that the benchmark draws from.

---

# 03133

**Repository:** yangyun114/etcd3

**PBT Summary:** When using `etcdctl` to put a key-value pair in etcd, retrieving the key using `get` in serializable mode should return the same value, even when quorum nodes are temporarily stopped.

**Total Unit Tests:** 48


**Unit Test 1:**
```python
def test_get_unknown_key(self, etcd):
        value, meta = etcd.get('probably-invalid-key')
        assert value is None
        assert meta is None
```

**Unit Test 2:**
```python
def test_nested_transactions(self, etcd):
        etcd.transaction(
            compare=[],
            success=[etcd.transactions.put('/doot/txn1', '1'),
                     etcd.transactions.txn(
                         compare=[],
                         success=[etcd.transactions.put('/doot/txn2', '2')],
                         failure=[])],
            failure=[]
        )
        value, _ = etcd.get('/doot/txn1')
        assert value == b'1'
        value, _ = etcd.get('/doot/txn2')
        assert value == b'2'
```

**Unit Test 3:**
```python
def test_replace_success(self, etcd):
        etcd.put('/doot/thing', 'toot')
        status = etcd.replace('/doot/thing', 'toot', 'doot')
        v, _ = etcd.get('/doot/thing')
        assert v == b'doot'
        assert status is True
```

**Unit Test 4:**
```python
def test_replace_fail(self, etcd):
        etcd.put('/doot/thing', 'boot')
        status = etcd.replace('/doot/thing', 'toot', 'doot')
        v, _ = etcd.get('/doot/thing')
        assert v == b'boot'
        assert status is False
```

**Unit Test 5:**
```python
def test_lease_expire(self, etcd):
        key = '/doot/lease_test_expire'
        lease = etcd.lease(1)
        etcd.put(key, 'this is a lease', lease=lease)
        assert lease.keys == [utils.to_bytes(key)]
        v, _ = etcd.get(key)
        assert v == b'this is a lease'
        assert lease.remaining_ttl <= lease.granted_ttl

        # wait for the lease to expire
        time.sleep(lease.granted_ttl + 2)
        v, _ = etcd.get(key)
        assert v is None
```


# 17533

**Repository:** scikit-shapes/scikit-shapes

**PBT Summary:** The `Multiscale` class for triangle meshes should correctly handle signal propagation through different resolutions, ensuring consistency of signal transformation and composition through multiple scales while adhering to the specified policies for reducing and smoothing signals.

**Total Unit Tests:** 59


**Unit Test 1:**
```python
def test_curvatures_quadratic(
    *,
    n_points: int,
    a: float,
    b: float,
    c: float,
    d: float,
    e: float,
    f: float,
):
    """Test the curvatures of a quadratic function."""
    # Our current estimation method relies on the estimation of the tangent
    # plane, and does not give perfect results for quadratic functions "off
    # center".
    # See e.g. the function f(x,y) = y**2 + y.
    #
    # Another issue is a fairly large variance for very large values of the
    # coefficients,
    # e.g. f(x,y) = 2 * x * y
    d = 0 * d
    e = 0 * e

    def poly(x, y):
        return 0.5 * a * x**2 + b * x * y + 0.5 * c * y**2 + d * x + e * y + f

    # See Example 4.2 in Curvature formulas for implicit curves and surfaces,
    # Goldman, 2005, for reference on those formulas, keeping in mind that
    # Grad(f) = (d, e) and H(f) = [[a, b], [b, c]].
    denom = 1 + d**2 + e**2  # 1 + ||Grad(f)||^2
    gauss = a * c - b * b  # det(H(f))
    gauss = gauss / denom**2

    # Term 1: Grad(f)^T . H(f) . Grad(f)
    mean = d * d * a + 2 * d * e * b + e * e * c
    # Term 2: - (1 + ||Grad(f)||^2) * trace(H(f))
    mean = mean - denom * (a + c)
    mean = mean / (2 * denom ** (1.5))
    # Our convention for unoriented point clouds is that the mean curvature
    # is >= 0:
    mean = np.abs(mean)

    # Create a point clouds around [0, 0] in the (x,y) plane and compute
    # z = f(x, y).
    # Point shape.points[0] = [0, 0, f(0, 0)]
    shape = create_shape(shape="unit patch", n_points=n_points, function=poly)

    scales = [0.8, 1]

    for scale in scales:
        kmax, kmin = shape.point_principal_curvatures(scale=scale)
        return
        kmax = kmax[0].item()
        kmin = kmin[0].item()
        assert kmax * kmin == pytest.approx(gauss, abs=5e-1, rel=2e-1)
        assert (kmax + kmin) / 2 == pytest.approx(mean, abs=5e-1, rel=2e-1)
```

**Unit Test 2:**
```python
def test_curvatures_sphere(
    *, n_points: int, radius: float, relative_scale: float
):
    """Test the curvatures of a sphere."""
    # Create a sphere with the correct radius and an arbitrary center:
    shape = create_shape(shape="sphere", n_points=n_points, radius=radius)

    ones = torch.ones_like(shape.points[:, 0])

    scale = relative_scale * radius
    kmax, kmin = shape.point_principal_curvatures(scale=scale)
    assert torch.allclose(kmax, ones / radius, atol=1e-1, rtol=1e-1)
    assert torch.allclose(kmin, ones / radius, atol=1e-1, rtol=1e-1)
```

**Unit Test 3:**
```python
def test_geometry_features():
    """Test some geometry features on a simple mesh."""
    square_points = torch.tensor(
        [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=sks.float_dtype
    )
    square_edges = torch.tensor(
        [[0, 1], [1, 2], [2, 3], [3, 0]], dtype=sks.int_dtype
    )
    square = sks.PolyData(points=square_points, edges=square_edges)
    assert square.n_edges == 4

    with pytest.raises(AttributeError, match="Triangles are not defined"):
        square.triangle_centroids  # noqa: B018 (useless expression)
    with pytest.raises(AttributeError, match="Triangles are not defined"):
        square.triangle_normals  # noqa: B018 (useless expression)

    assert torch.allclose(
        square.point_masses, torch.tensor([1, 1, 1, 1], dtype=sks.float_dtype)
    )

    assert torch.allclose(
        square.edge_lengths, torch.tensor([1, 1, 1, 1], dtype=sks.float_dtype)
    )

    assert torch.allclose(
        square.edge_midpoints,
        torch.tensor(
            [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]], dtype=sks.float_dtype
        ),
    )

    assert torch.allclose(
        square.mean_point, torch.tensor([0.5, 0.5], dtype=sks.float_dtype)
    )

    assert torch.allclose(
        square.standard_deviation,
        torch.tensor([0.5, 0.5], dtype=sks.float_dtype).sqrt(),
    )

    triangle_points = torch.tensor(
        [[0, 0], [1, 0], [0, 1]], dtype=sks.float_dtype
    )
    triangle_triangles = torch.tensor([[0, 1, 2]], dtype=sks.int_dtype)

    triangle = sks.PolyData(
        points=triangle_points, triangles=triangle_triangles
    )
    assert triangle.n_edges == 3
    assert triangle.n_triangles == 1
    assert torch.allclose(
        triangle.triangle_areas, torch.tensor([0.5], dtype=sks.float_dtype)
    )

    assert torch.allclose(
        triangle.triangle_centroids,
        torch.tensor([[1 / 3, 1 / 3]], dtype=sks.float_dtype),
    )

    assert torch.allclose(
        triangle.triangle_normals,
        torch.tensor([[0, 0, 1]], dtype=sks.float_dtype),
    )

    pointcloud = sks.PolyData(triangle.points)

    for attribute in [
        "triangle_areas",
        "triangle_centroids",
        "edge_lengths",
        "edge_midpoints",
    ]:
        with pytest.raises(AttributeError):
            getattr(pointcloud, attribute)
```

**Unit Test 4:**
```python
def test_polydata_creation_2d():
    """Test manually creating a 2d mesh + interaction with pv/vedo."""
    points = torch.tensor([[0, 0], [0, 1], [1, 0]], dtype=torch.float64)
    triangles = torch.tensor([[0, 1, 2]], dtype=torch.int32)

    flat_triangle = sks.PolyData(points=points, triangles=triangles)
    assert flat_triangle.dim == 2
    assert flat_triangle.n_triangles == 1
    assert flat_triangle.n_edges == 3

    # to_pyvista creates a z-coordinate equal to 0
    pv_mesh = flat_triangle.to_pyvista()
    assert pv_mesh.points.shape == (3, 3)
    assert np.allclose(pv_mesh.points[:, 2], 0)
    mesh_back = sks.PolyData(pv_mesh)
    assert mesh_back.dim == 2

    vedo_mesh = flat_triangle.to_vedo()
    assert vedo_mesh.points.shape == (3, 3)
    assert np.allclose(vedo_mesh.points[:, 2], 0)
    mesh_back = sks.PolyData(vedo_mesh)
    assert mesh_back.dim == 2
```

**Unit Test 5:**
```python
def test_interaction_with_pyvista():
    """Test the interaction with pyvista."""
    # Import/export from/to pyvista
    from pyvista.examples import load_sphere

    mesh = load_sphere()
    n_points = mesh.n_points
    n_triangles = mesh.n_cells

    # Create a PolyData from a pyvista mesh
    polydata = sks.PolyData(mesh)
    assert polydata.n_points == n_points
    assert polydata.n_triangles == n_triangles

    # back to pyvista, check that the mesh is the same
    mesh2 = polydata.to_pyvista()
    assert np.allclose(mesh.points, mesh2.points)
    assert np.allclose(mesh.faces, mesh2.faces)

    # Open a quadratic mesh
    cube = _cube()
    # the cube is a polydata with 6 cells (quads) and 8 points
    assert not cube.is_all_triangles
    assert cube.n_cells == 6
    assert cube.n_points == 8
    # Create a PolyData from a pyvista mesh and check that the faces are
    # converted to triangles
    polydata = sks.PolyData(cube)
    assert polydata.n_points == 8
    assert polydata.n_triangles == 12
    # back to pyvista, check that the mesh is the same
    cube2 = polydata.to_pyvista()
    assert cube2.n_cells == 12
    assert cube2.n_points == 8
    assert cube2.is_all_triangles
    assert np.allclose(cube.points, cube2.points)

    # Importing a point cloud from pyvsita
    n = 100
    points = np.random.default_rng().random(size=(n, 3))
    polydata = pyvista.PolyData(points)
    mesh = sks.PolyData(polydata)
    assert mesh.n_points == n
    assert mesh.n_triangles == 0
    assert mesh.n_edges == 0
```


# 22773

**Repository:** jroth2858/lfsr-tools

**PBT Summary:** LSFR instantiation should correctly match the initial state with the seed for various polynomial and seed combinations, handling exceptions for degenerate polynomials and invalid seeds as specified.

**Total Unit Tests:** 5


**Unit Test 1:**
```python
def test_lfsr_instantiation(poly_seed):
    ''' This test checks LSFR instantiation with various polynomial/seed combinations.
    Edge cases with reducible polynomials, polynomials with 0 coefficients in the MSB
    positions, and all zero seeds are also checked.
    '''
    poly, seed = poly_seed
    try:
        lfsr = LFSR(poly=poly,
                    seed=seed,
                    )
        for i, j in zip(lfsr.state, seed):
            assert i == j
        
        assert len(lfsr) == len(lfsr.state) # check __len__

    except PolynomialError:
        '''Degenerate polynomials are either all zero or only have a 1 in the LSBs place.'''
        assert (np.sum(poly) == 0) or ((poly[0]==1) and (np.sum(poly)==1))

    except SeedError:
        '''Bad seeds are all zero, everything else is fine.'''
        extended_seed = np.r_[0, seed] #Extend the seed to the same length as the polynomial
        poly_mask = np.zeros(len(poly)).astype(int)
        poly_mask_idx = utils.find_most_significant_bit(poly)
        poly_mask[:poly_mask_idx+1] = 1
        test_string = extended_seed & poly_mask #
        assert np.sum(test_string) == 0 #Check the remaining seed bits to make sure there is at least one remaining nonzero bit
```

**Unit Test 2:**
```python
def test_lfsr_iteration(poly_sets = [POLY1, POLY2, POLY3, POLY4, POLY5]):
    ''' Check that the correct m-sequence is output for each primitive 
    polynomial up to order five.
    '''
    def check_correlation_property(bits):
        corr = utils.circular_autocorrelation(bits, mode='bpsk')
        zerolag = (int(corr[0])==len(corr))
        nonzerolag = np.all(np.isclose(np.real(corr[1:]), -1))

        assert zerolag and nonzerolag

    for poly_set in poly_sets:
        for poly in poly_set:
            lfsr = LFSR(poly=poly)
            bits = []
            for bit in lfsr: #Test __iter__
                bits.append(bit)
            
            assert len(bits) == lfsr.max_seq_len #Check for correct number of states
            assert np.sum(bits) == 2**(len(lfsr)-1) #Check balance property
            check_correlation_property(bits) # Checks correlation property
```

**Unit Test 3:**
```python
def test_bm_primitive_impl(poly_sets = [POLY1, POLY2, POLY3, POLY4, POLY5]):
    ''' Generate a sequence with a LFSR and then verify that the polynomial 
    can be recovered with Berlekamp Massey. Tests all primitive polynomials
    of order 5 or less.
    '''
    for poly_set in poly_sets:
        for polynomial in poly_set:
            lfsr = LFSR(poly=polynomial)
            sequence = [bit for bit in lfsr]
            bkm = BerlekampMassey(sequence=sequence)
            bkm.estimate_polynomial()
            assert np.all(bkm.est_poly == polynomial)
```

**Unit Test 4:**
```python
def test_bm_nonprimitive_impl(poly):
    ''' Tests selected (primitive or nonprimitive) polynomials up to and including degree 5.
    Only polynomials of the form 1 + ... + x^(max_size-1) are allowed. The Berlekamp-Massey
    implementation fails otherwise.
    '''
    lfsr = LFSR(poly=poly)
    sequence = [bit for bit in lfsr]
    bkm = BerlekampMassey(sequence=sequence)
    bkm.estimate_polynomial()
    assert np.all(bkm.est_poly == poly)
```

**Unit Test 5:**
```python
def test_bm_nonprimitive_degenerate_impl(poly):
    ''' Tests all (primitive or nonprimitive) polynomials up to and including degree 5.
    '''
    lfsr = LFSR(poly=poly)
    sequence = [bit for bit in lfsr]
    bkm = BerlekampMassey(sequence=sequence)
    bkm.estimate_polynomial()
    assert np.all(bkm.est_poly == poly)
```


# 32463

**Repository:** cgevans/kithairon

**PBT Summary:** The destination movement distance between two sets of source and destination wells should be zero when offsets by integer steps are applied consistently to both the source and destination well tuples.

**Total Unit Tests:** 5


**Unit Test 1:**
```python
def test_zero_dest_motion_steps_384_384(s1: str, d1: str, mrow: int, mcol: int):
    s1t = well_to_tuple(s1)
    d1t = well_to_tuple(d1)

    s2t = (s1t[0] + mrow, s1t[1] + mcol)
    d2t = (d1t[0] + mrow, d1t[1] - mcol)
    if (
        (d2t[0] < 0)
        or (d2t[0] >= 16)
        or (d2t[1] < 0)
        or (d2t[1] >= 24)
        or (s2t[0] < 0)
        or (s2t[0] >= 16)
        or (s2t[1] < 0)
        or (s2t[1] >= 24)
    ):
        return
    s2 = tuple_to_well(s2t)
    d2 = tuple_to_well(d2t)

    assert _dest_motion_distance_by_wells(s1, d1, s2, d2) == 0
```

**Unit Test 2:**
```python
def test_zero_dest_motion_steps_96_96(s1: str, d1: str, mrow: int, mcol: int):
    s1t = well_to_tuple(s1)
    d1t = well_to_tuple(d1)

    s2t = (s1t[0] + mrow, s1t[1] + mcol)
    d2t = (d1t[0] + mrow, d1t[1] - mcol)
    if (
        (d2t[0] < 0)
        or (d2t[0] >= 8)
        or (d2t[1] < 0)
        or (d2t[1] >= 12)
        or (s2t[0] < 0)
        or (s2t[0] >= 8)
        or (s2t[1] < 0)
        or (s2t[1] >= 12)
    ):
        return
    s2 = tuple_to_well(s2t)
    d2 = tuple_to_well(d2t)

    assert _dest_motion_distance_by_wells(s1, d1, s2, d2, 9.0, 9.0, 9.0, 9.0) == 0
```

**Unit Test 3:**
```python
def test_zero_dest_motion_steps_384_96(s1: str, d1: str, mrow: int, mcol: int):
    s1t = well_to_tuple(s1)
    d1t = well_to_tuple(d1)

    s2t = (s1t[0] + 2 * mrow, s1t[1] + 2 * mcol)
    d2t = (d1t[0] + mrow, d1t[1] - mcol)
    if (
        (d2t[0] < 0)
        or (d2t[0] >= 8)
        or (d2t[1] < 0)
        or (d2t[1] >= 12)
        or (s2t[0] < 0)
        or (s2t[0] >= 16)
        or (s2t[1] < 0)
        or (s2t[1] >= 24)
    ):
        return
    s2 = tuple_to_well(s2t)
    d2 = tuple_to_well(d2t)

    assert _dest_motion_distance_by_wells(s1, d1, s2, d2, 4.5, 4.5, 9.0, 9.0) == 0
```

**Unit Test 4:**
```python
def test_basic_zero_dest_motion_steps():
    assert _dest_motion_distance_by_wells("A1", "A1", "A1", "A1") == 0
    assert _dest_motion_distance_by_wells("A1", "A24", "A24", "A1") == 0
    assert _dest_motion_distance_by_wells("A2", "P23", "A23", "P2") == 0
```

**Unit Test 5:**
```python
def test_transducer_motion_distance(s1, di, dj, d1, d2, sx, sy, dx, dy):
    s1t = well_to_tuple(s1)
    s2t = (s1t[0] + di, s1t[1] + dj)
    if (s2t[0] < 0) or (s2t[0] >= 16) or (s2t[1] < 0) or (s2t[1] >= 24):
        return
    s2 = tuple_to_well(s2t)

    assert _transducer_motion_distance_by_wells(
        s1, d1, s2, d2, sx, sy, dx, dy
    ) == sy * abs(di) + sx * abs(dj)
```


# 36563

**Repository:** LunaPurpleSunshine/test-repo

**PBT Summary:** The function `rando.custom_namer` correctly appends the current date between `stem` and `suffix` in the input string.

**Total Unit Tests:** 6


**Unit Test 1:**
```python
def test_expected_input(self, stem: str, suffix: str):
        assume(all([stem, suffix]))

        input_name = f"{stem}.{suffix}"
        expected_output = f"{stem}.{datetime.now().date()}.{suffix}"

        result = rando.custom_namer(input_name)

        assert result == expected_output
```

**Unit Test 2:**
```python
def test_multiple_suffixes(self, stem, suffix):
        assume(all([stem, suffix]))

        input_name = f"{stem}.{suffix}.{suffix}"
        expected_output = f"{stem}.{suffix}.{datetime.now().date()}.{suffix}"

        result = rando.custom_namer(input_name)

        assert result == expected_output
```

**Unit Test 3:**
```python
def test_not_str(self, name):
        with pytest.raises(TypeError):
            rando.custom_namer(name)
```

**Unit Test 4:**
```python
def test_invalid_input_stem(self, suffix):
        name = f".{suffix}"
        with pytest.raises(ValueError):
            rando.custom_namer(name)
```

**Unit Test 5:**
```python
def test_invalid_input_suffix(self, stem):
        name = f"{stem}"
        with pytest.raises(ValueError):
            rando.custom_namer(name)
```


# 40001

**Repository:** sailfishos-mirror/cpython

**PBT Summary:** No summary available

**Total Unit Tests:** 278


**Unit Test 1:**
```python
def test_pickle(self):
        async def func(): pass
        coro = func()
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            with self.assertRaises((TypeError, pickle.PicklingError)):
                pickle.dumps(coro, proto)

        aw = coro.__await__()
        try:
            for proto in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.assertRaises((TypeError, pickle.PicklingError)):
                    pickle.dumps(aw, proto)
        finally:
            aw.close()
```

**Unit Test 2:**
```python
def test_subinterpreter_stack_trace(self):
        # Test that subinterpreters are correctly handled
        port = find_unused_port()

        # Calculate subinterpreter code separately and pickle it to avoid f-string issues
        import pickle
        subinterp_code = textwrap.dedent(f'''
            import socket
            import time

            def sub_worker():
                def nested_func():
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', {port}))
                    sock.sendall(b"ready:sub\\n")
                    time.sleep(10_000)
                nested_func()

            sub_worker()
        ''').strip()

        # Pickle the subinterpreter code
        pickled_code = pickle.dumps(subinterp_code)

        script = textwrap.dedent(
            f"""
            from concurrent import interpreters
            import time
            import sys
            import socket
            import threading

            # Connect to the test process
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('localhost', {port}))

            def main_worker():
                # Function running in main interpreter
                sock.sendall(b"ready:main\\n")
                time.sleep(10_000)

            def run_subinterp():
                # Create and run subinterpreter
                subinterp = interpreters.create()

                import pickle
                pickled_code = {pickled_code!r}
                subinterp_code = pickle.loads(pickled_code)
                subinterp.exec(subinterp_code)

            # Start subinterpreter in thread
            sub_thread = threading.Thread(target=run_subinterp)
            sub_thread.start()

            # Start main thread work
            main_thread = threading.Thread(target=main_worker)
            main_thread.start()

            # Keep main thread alive
            main_thread.join()
            sub_thread.join()
            """
        )

        with os_helper.temp_dir() as work_dir:
            script_dir = os.path.join(work_dir, "script_pkg")
            os.mkdir(script_dir)

            # Create a socket server to communicate with the target process
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", port))
            server_socket.settimeout(SHORT_TIMEOUT)
            server_socket.listen(1)

            script_name = _make_test_script(script_dir, "script", script)
            client_sockets = []
            try:
                p = subprocess.Popen([sys.executable, script_name])

                # Accept connections from both main and subinterpreter
                responses = set()
                while len(responses) < 2:  # Wait for both "ready:main" and "ready:sub"
                    try:
                        client_socket, _ = server_socket.accept()
                        client_sockets.append(client_socket)

                        # Read the response from this connection
                        response = client_socket.recv(1024)
                        if b"ready:main" in response:
                            responses.add("main")
                        if b"ready:sub" in response:
                            responses.add("sub")
                    except socket.timeout:
                        break

                server_socket.close()
                stack_trace = get_stack_trace(p.pid)
            except PermissionError:
                self.skipTest(
                    "Insufficient permissions to read the stack trace"
                )
            finally:
                for client_socket in client_sockets:
                    if client_socket is not None:
                        client_socket.close()
                p.kill()
                p.terminate()
                p.wait(timeout=SHORT_TIMEOUT)

            # Verify we have multiple interpreters
            self.assertGreaterEqual(len(stack_trace), 1, "Should have at least one interpreter")

            # Look for main interpreter (ID 0) and subinterpreter (ID > 0)
            main_interp = None
            sub_interp = None

            for interpreter_info in stack_trace:
                if interpreter_info.interpreter_id == 0:
                    main_interp = interpreter_info
                elif interpreter_info.interpreter_id > 0:
                    sub_interp = interpreter_info

            self.assertIsNotNone(main_interp, "Main interpreter should be present")

            # Check main interpreter has expected stack trace
            main_found = False
            for thread_info in main_interp.threads:
                for frame in thread_info.frame_info:
                    if frame.funcname == "main_worker":
                        main_found = True
                        break
                if main_found:
                    break
            self.assertTrue(main_found, "Main interpreter should have main_worker in stack")

            # If subinterpreter is present, check its stack trace
            if sub_interp:
                sub_found = False
                for thread_info in sub_interp.threads:
                    for frame in thread_info.frame_info:
                        if frame.funcname in ("sub_worker", "nested_func"):
                            sub_found = True
                            break
                    if sub_found:
                        break
                self.assertTrue(sub_found, "Subinterpreter should have sub_worker or nested_func in stack")
```

**Unit Test 3:**
```python
def test_multiple_subinterpreters_with_threads(self):
        # Test multiple subinterpreters, each with multiple threads
        port = find_unused_port()

        # Calculate subinterpreter codes separately and pickle them
        import pickle

        # Code for first subinterpreter with 2 threads
        subinterp1_code = textwrap.dedent(f'''
            import socket
            import time
            import threading

            def worker1():
                def nested_func():
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', {port}))
                    sock.sendall(b"ready:sub1-t1\\n")
                    time.sleep(10_000)
                nested_func()

            def worker2():
                def nested_func():
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', {port}))
                    sock.sendall(b"ready:sub1-t2\\n")
                    time.sleep(10_000)
                nested_func()

            t1 = threading.Thread(target=worker1)
            t2 = threading.Thread(target=worker2)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        ''').strip()

        # Code for second subinterpreter with 2 threads
        subinterp2_code = textwrap.dedent(f'''
            import socket
            import time
            import threading

            def worker1():
                def nested_func():
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', {port}))
                    sock.sendall(b"ready:sub2-t1\\n")
                    time.sleep(10_000)
                nested_func()

            def worker2():
                def nested_func():
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(('localhost', {port}))
                    sock.sendall(b"ready:sub2-t2\\n")
                    time.sleep(10_000)
                nested_func()

            t1 = threading.Thread(target=worker1)
            t2 = threading.Thread(target=worker2)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        ''').strip()

        # Pickle the subinterpreter codes
        pickled_code1 = pickle.dumps(subinterp1_code)
        pickled_code2 = pickle.dumps(subinterp2_code)

        script = textwrap.dedent(
            f"""
            from concurrent import interpreters
            import time
            import sys
            import socket
            import threading

            # Connect to the test process
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('localhost', {port}))

            def main_worker():
                # Function running in main interpreter
                sock.sendall(b"ready:main\\n")
                time.sleep(10_000)

            def run_subinterp1():
                # Create and run first subinterpreter
                subinterp = interpreters.create()

                import pickle
                pickled_code = {pickled_code1!r}
                subinterp_code = pickle.loads(pickled_code)
                subinterp.exec(subinterp_code)

            def run_subinterp2():
                # Create and run second subinterpreter
                subinterp = interpreters.create()

                import pickle
                pickled_code = {pickled_code2!r}
                subinterp_code = pickle.loads(pickled_code)
                subinterp.exec(subinterp_code)

            # Start subinterpreters in threads
            sub1_thread = threading.Thread(target=run_subinterp1)
            sub2_thread = threading.Thread(target=run_subinterp2)
            sub1_thread.start()
            sub2_thread.start()

            # Start main thread work
            main_thread = threading.Thread(target=main_worker)
            main_thread.start()

            # Keep main thread alive
            main_thread.join()
            sub1_thread.join()
            sub2_thread.join()
            """
        )

        with os_helper.temp_dir() as work_dir:
            script_dir = os.path.join(work_dir, "script_pkg")
            os.mkdir(script_dir)

            # Create a socket server to communicate with the target process
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", port))
            server_socket.settimeout(SHORT_TIMEOUT)
            server_socket.listen(5)  # Allow multiple connections

            script_name = _make_test_script(script_dir, "script", script)
            client_sockets = []
            try:
                p = subprocess.Popen([sys.executable, script_name])

                # Accept connections from main and all subinterpreter threads
                expected_responses = {"ready:main", "ready:sub1-t1", "ready:sub1-t2", "ready:sub2-t1", "ready:sub2-t2"}
                responses = set()

                while len(responses) < 5:  # Wait for all 5 ready signals
                    try:
                        client_socket, _ = server_socket.accept()
                        client_sockets.append(client_socket)

                        # Read the response from this connection
                        response = client_socket.recv(1024)
                        response_str = response.decode().strip()
                        if response_str in expected_responses:
                            responses.add(response_str)
                    except socket.timeout:
                        break

                server_socket.close()
                stack_trace = get_stack_trace(p.pid)
            except PermissionError:
                self.skipTest(
                    "Insufficient permissions to read the stack trace"
                )
            finally:
                for client_socket in client_sockets:
                    if client_socket is not None:
                        client_socket.close()
                p.kill()
                p.terminate()
                p.wait(timeout=SHORT_TIMEOUT)

            # Verify we have multiple interpreters
            self.assertGreaterEqual(len(stack_trace), 2, "Should have at least two interpreters")

            # Count interpreters by ID
            interpreter_ids = {interp.interpreter_id for interp in stack_trace}
            self.assertIn(0, interpreter_ids, "Main interpreter should be present")
            self.assertGreaterEqual(len(interpreter_ids), 3, "Should have main + at least 2 subinterpreters")

            # Count total threads across all interpreters
            total_threads = sum(len(interp.threads) for interp in stack_trace)
            self.assertGreaterEqual(total_threads, 5, "Should have at least 5 threads total")

            # Look for expected function names in stack traces
            all_funcnames = set()
            for interpreter_info in stack_trace:
                for thread_info in interpreter_info.threads:
                    for frame in thread_info.frame_info:
                        all_funcnames.add(frame.funcname)

            # Should find functions from different interpreters and threads
            expected_funcs = {"main_worker", "worker1", "worker2", "nested_func"}
            found_funcs = expected_funcs.intersection(all_funcnames)
            self.assertGreater(len(found_funcs), 0, f"Should find some expected functions, got: {all_funcnames}")
```

**Unit Test 4:**
```python
def test_pickle_slots(self):
        # Tests pickling of classes with __slots__.

        # Pickling of classes with __slots__ but without __getstate__ should
        # fail (if using protocol 0 or 1)
        global C
        class C:
            __slots__ = ['a']
        with self.assertRaises(TypeError):
            pickle.dumps(C(), 0)

        global D
        class D(C):
            pass
        with self.assertRaises(TypeError):
            pickle.dumps(D(), 0)

        class C:
            "A class with __getstate__ and __setstate__ implemented."
            __slots__ = ['a']
            def __getstate__(self):
                state = getattr(self, '__dict__', {}).copy()
                for cls in type(self).__mro__:
                    for slot in cls.__dict__.get('__slots__', ()):
                        try:
                            state[slot] = getattr(self, slot)
                        except AttributeError:
                            pass
                return state
            def __setstate__(self, state):
                for k, v in state.items():
                    setattr(self, k, v)
            def __repr__(self):
                return "%s()<%r>" % (type(self).__name__, self.__getstate__())

        class D(C):
            "A subclass of a class with slots."
            pass

        global E
        class E(C):
            "A subclass with an extra slot."
            __slots__ = ['b']

        # Now it should work
        for pickle_copier in self._generate_pickle_copiers():
            with self.subTest(pickle_copier=pickle_copier):
                x = C()
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x.a = 42
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x = D()
                x.a = 42
                x.b = 100
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x = E()
                x.a = 42
                x.b = "foo"
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)
```

**Unit Test 5:**
```python
def test_pickle(self):
        a = ET.Element('a')
        it = a.iter()
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            with self.assertRaises((TypeError, pickle.PicklingError)):
                pickle.dumps(it, proto)
```


# 44970

**Repository:** kalzaroo/esphome

**PBT Summary:** No summary available

**Total Unit Tests:** 2


**Unit Test 1:**
```python
def test_string__valid(value):
    actual = config_validation.string(value)

    assert actual == str(value)
```

**Unit Test 2:**
```python
def test_string__invalid(value):
    with pytest.raises(Invalid):
        config_validation.string(value)
```


# 53839

**Repository:** litestar-org/pydantic-factories

**PBT Summary:** The `is_multiply_of_multiple_of_in_range` function returns `True` if there exists a multiple of `multiple_of` within the specified range and `False` otherwise, when evaluated with generated floats and integers as inputs.

**Total Unit Tests:** 8


**Unit Test 1:**
```python
def test_is_multiply_of_multiple_of_in_range_extreme_cases() -> None:
    assert is_multiply_of_multiple_of_in_range(minimum=None, maximum=10.0, multiple_of=20.0)
    assert not is_multiply_of_multiple_of_in_range(minimum=5.0, maximum=10.0, multiple_of=20.0)

    assert is_multiply_of_multiple_of_in_range(minimum=1.0, maximum=1.0, multiple_of=0.33333333333)
    assert is_multiply_of_multiple_of_in_range(
        minimum=Decimal(1), maximum=Decimal(1), multiple_of=Decimal("0.33333333333")
    )
    assert not is_multiply_of_multiple_of_in_range(minimum=Decimal(1), maximum=Decimal(1), multiple_of=Decimal("0.333"))

    assert is_multiply_of_multiple_of_in_range(minimum=5, maximum=5, multiple_of=5)

    # while multiple_of=0.0 leads to ZeroDivision exception in pydantic
    # it can handle values close to zero properly so we should support this too
    assert is_multiply_of_multiple_of_in_range(minimum=10.0, maximum=20.0, multiple_of=1e-10)
    # test corner case found by peterschutt
    assert not is_multiply_of_multiple_of_in_range(
        minimum=Decimal("999999999.9999999343812775"),
        maximum=Decimal("999999999.990476"),
        multiple_of=Decimal("-0.556"),
    )
```

**Unit Test 2:**
```python
def test_handle_constrained_int_handles_multiple_of_with_ge_and_le(val1: int, val2: int, val3: int) -> None:
    min_value, multiple_of, max_value = sorted([val1, val2, val3])
    if multiple_of != 0 and is_multiply_of_multiple_of_in_range(
        minimum=min_value, maximum=max_value, multiple_of=multiple_of
    ):
        result = handle_constrained_int(create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value))
        assert passes_pydantic_multiple_validator(result, multiple_of)
    else:
        with pytest.raises(ParameterError):
            handle_constrained_int(create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value))
```

**Unit Test 3:**
```python
def test_handle_constrained_decimal_handles_multiple_of_with_ge_and_le(
    val1: Decimal, val2: Decimal, val3: Decimal
) -> None:
    min_value, multiple_of, max_value = sorted([val1, val2, val3])
    if multiple_of != Decimal("0") and is_multiply_of_multiple_of_in_range(
        minimum=min_value, maximum=max_value, multiple_of=multiple_of
    ):
        result = handle_constrained_decimal(
            create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value)
        )
        assert passes_pydantic_multiple_validator(result, multiple_of)
    else:
        with pytest.raises(ParameterError):
            handle_constrained_decimal(create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value))
```

**Unit Test 4:**
```python
def test_handle_constrained_float_handles_multiple_of_with_ge_and_le(val1: float, val2: float, val3: float) -> None:
    min_value, multiple_of, max_value = sorted([val1, val2, val3])
    if multiple_of != 0.0 and is_multiply_of_multiple_of_in_range(
        minimum=min_value, maximum=max_value, multiple_of=multiple_of
    ):
        result = handle_constrained_float(create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value))
        assert passes_pydantic_multiple_validator(result, multiple_of)
    else:
        with pytest.raises(ParameterError):
            handle_constrained_float(create_constrained_field(multiple_of=multiple_of, ge=min_value, le=max_value))
```

**Unit Test 5:**
```python
def test_is_multiply_of_multiple_of_in_range_for_floats(base_multiple_of: float, multiplier: int) -> None:
    if multiplier != 0:
        for multiple_of in [base_multiple_of, -base_multiple_of]:
            minimum, maximum = sorted(
                [
                    multiplier * multiple_of + random.random() * 100,
                    (multiplier + random.randint(1, 100)) * multiple_of + random.random() * 100,
                ]
            )
            assert is_multiply_of_multiple_of_in_range(minimum=minimum, maximum=maximum, multiple_of=multiple_of)

            minimum, maximum = sorted(
                [
                    (multiplier + (random.random() / 2 + 0.01)) * multiple_of,
                    (multiplier + (random.random() / 2 + 0.45)) * multiple_of,
                ]
            )
            assert not is_multiply_of_multiple_of_in_range(minimum=minimum, maximum=maximum, multiple_of=multiple_of)
```


# 44075

**Repository:** CyberFlameGO/sqlfluff

**PBT Summary:** No summary available

**Total Unit Tests:** 68


**Unit Test 1:**
```python
def test__linter__path_from_paths__exts():
    """Test configuration of file discovery."""
    lntr = Linter(config=FluffConfig(overrides={"sql_file_exts": ".txt"}))
    paths = normalise_paths(lntr.paths_from_path("test/fixtures/linter"))
    assert "test.fixtures.linter.passing.sql" not in paths
    assert "test.fixtures.linter.discovery_file.txt" in paths
```

**Unit Test 2:**
```python
def test_lint_path_parallel_wrapper_exception(patched_lint):
    """Tests the error catching behavior of _lint_path_parallel_wrapper().

    Test on MultiThread runner because otherwise we have pickling issues.
    """
    patched_lint.side_effect = ValueError("Something unexpected happened")
    for result in runner.MultiThreadRunner(Linter(), FluffConfig(), processes=1).run(
        ["test/fixtures/linter/passing.sql"],
        fix=False,
    ):
        assert isinstance(result, runner.DelayedException)
        with pytest.raises(ValueError):
            result.reraise()
```

**Unit Test 3:**
```python
def test__linter__mask_templated_violations(ignore_templated_areas, check_tuples):
    """Test linter masks files properly around templated content."""
    lntr = Linter(
        config=FluffConfig(
            overrides={
                "rules": "L006",
                "ignore_templated_areas": ignore_templated_areas,
            }
        )
    )
    linted = lntr.lint_path(path="test/fixtures/templater/jinja_h_macros/jinja.sql")
    assert linted.check_tuples() == check_tuples
```

**Unit Test 4:**
```python
def test__linter__encoding(fname, config_encoding, lexerror):
    """Test linter deals with files with different encoding."""
    lntr = Linter(
        config=FluffConfig(
            overrides={
                "rules": "L001",
                "encoding": config_encoding,
            }
        )
    )
    result = lntr.lint_paths([fname])
    assert lexerror == (SQLLexError in [type(v) for v in result.get_violations()])
```

**Unit Test 5:**
```python
def test_linter_noqa():
    """Test "noqa" feature at the higher "Linter" level."""
    lntr = Linter(
        config=FluffConfig(
            overrides={
                "dialect": "bigquery",  # Use bigquery to allow hash comments.
                "rules": "L012, L019",
            }
        )
    )
    sql = """
    SELECT
        col_a a,
        col_b b, --noqa: disable=L012
        col_c c,
        col_d d, --noqa: enable=L012
        col_e e,
        col_f f,
        col_g g,  --noqa
        col_h h,
        col_i i, --noqa:L012
        col_j j,
        col_k k, --noqa:L013
        col_l l,
        col_m m,
        col_n n, --noqa: disable=all
        col_o o,
        col_p p, --noqa: enable=all
        col_q q, --Inline comment --noqa: L012
        col_r r, /* Block comment */ --noqa: L012
        col_s s # hash comment --noqa: L012
        -- We trigger both L012 (implicit aliasing)
        -- and L019 (leading commas) here to
        -- test glob ignoring of multiple rules.
        , col_t t --noqa: L01*
        , col_u u -- Some comment --noqa: L01*
        , col_v v -- We can ignore both L012 and L019 -- noqa: L01[29]
    FROM foo
        """
    result = lntr.lint_string(sql)
    violations = result.get_violations()
    assert {3, 6, 7, 8, 10, 12, 13, 14, 15, 18} == {v.line_no for v in violations}
```


# 08125

**Repository:** blhsing/cpython

**PBT Summary:** No summary available

**Total Unit Tests:** 273


**Unit Test 1:**
```python
def test_pickle(self):
        async def func(): pass
        coro = func()
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            with self.assertRaises((TypeError, pickle.PicklingError)):
                pickle.dumps(coro, proto)

        aw = coro.__await__()
        try:
            for proto in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.assertRaises((TypeError, pickle.PicklingError)):
                    pickle.dumps(aw, proto)
        finally:
            aw.close()
```

**Unit Test 2:**
```python
def test_pickle_slots(self):
        # Tests pickling of classes with __slots__.

        # Pickling of classes with __slots__ but without __getstate__ should
        # fail (if using protocol 0 or 1)
        global C
        class C:
            __slots__ = ['a']
        with self.assertRaises(TypeError):
            pickle.dumps(C(), 0)

        global D
        class D(C):
            pass
        with self.assertRaises(TypeError):
            pickle.dumps(D(), 0)

        class C:
            "A class with __getstate__ and __setstate__ implemented."
            __slots__ = ['a']
            def __getstate__(self):
                state = getattr(self, '__dict__', {}).copy()
                for cls in type(self).__mro__:
                    for slot in cls.__dict__.get('__slots__', ()):
                        try:
                            state[slot] = getattr(self, slot)
                        except AttributeError:
                            pass
                return state
            def __setstate__(self, state):
                for k, v in state.items():
                    setattr(self, k, v)
            def __repr__(self):
                return "%s()<%r>" % (type(self).__name__, self.__getstate__())

        class D(C):
            "A subclass of a class with slots."
            pass

        global E
        class E(C):
            "A subclass with an extra slot."
            __slots__ = ['b']

        # Now it should work
        for pickle_copier in self._generate_pickle_copiers():
            with self.subTest(pickle_copier=pickle_copier):
                x = C()
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x.a = 42
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x = D()
                x.a = 42
                x.b = 100
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)

                x = E()
                x.a = 42
                x.b = "foo"
                y = pickle_copier.copy(x)
                self._assert_is_copy(x, y)
```

**Unit Test 3:**
```python
def test_pickle(self):
        a = ET.Element('a')
        it = a.iter()
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            with self.assertRaises((TypeError, pickle.PicklingError)):
                pickle.dumps(it, proto)
```

**Unit Test 4:**
```python
def test_listen_config_10_ok(self):
        with support.captured_stdout() as output:
            self.setup_via_listener(json.dumps(self.config10))
            self.check_handler('hand1', logging.StreamHandler)
            logger = logging.getLogger("compiler.parser")
            logger.warning(self.next_message())
            logger = logging.getLogger('compiler')
            # Not output, because filtered
            logger.warning(self.next_message())
            logger = logging.getLogger('compiler.lexer')
            # Not output, because filtered
            logger.warning(self.next_message())
            logger = logging.getLogger("compiler.parser.codegen")
            # Output, as not filtered
            logger.error(self.next_message())
            self.assert_log_lines([
                ('WARNING', '1'),
                ('ERROR', '4'),
            ], stream=output)
```

**Unit Test 5:**
```python
def test_bug_5888452(self):
        # Simple-minded check for SF 588452: Debug build crashes
        marshal.dumps([128] * 1000)
```


# 44517

**Repository:** Dadudida-com/curve-stablecoin

**PBT Summary:** No summary available

**Total Unit Tests:** 96


**Unit Test 1:**
```python
def test_price(swap_w_d, redeemable_coin, volatile_coin, accounts, amount, ix):
    user = accounts[0]
    assert swap_w_d.get_p() == 10**18
    from_coin = [redeemable_coin, volatile_coin][ix]
    amount *= 10**(from_coin.decimals())
    with boa.env.prank(user):
        from_coin._mint_for_testing(user, amount)
        swap_w_d.exchange(ix, 1-ix, amount, 0)
        dy = swap_w_d.get_dy(0, 1, 10**6)
        p1 = 10**18 / dy
        p2 = swap_w_d.get_p() / 1e18
        assert approx(p1, p2, 0.04e-2 * 1.2)
```

**Unit Test 2:**
```python
def test_ema(swap_w_d, redeemable_coin, volatile_coin, accounts, amount, ix, dt0, dt):
    user = accounts[0]
    from_coin = [redeemable_coin, volatile_coin][ix]
    amount *= 10**(from_coin.decimals())
    with boa.env.prank(user):
        from_coin._mint_for_testing(user, amount)
        boa.env.time_travel(dt0)
        swap_w_d.exchange(ix, 1-ix, amount, 0)
        # Time didn't pass yet
        p = swap_w_d.get_p()
        assert approx(swap_w_d.last_price(), p, 1e-5)
        assert approx(swap_w_d.price_oracle(), 10**18, 1e-5)
        boa.env.time_travel(dt)
        w = exp(-dt / 866)
        p1 = int(10**18 * w + p * (1 - w))
        assert approx(swap_w_d.price_oracle(), p1, 1e-5)
```

**Unit Test 3:**
```python
def test_lm_callback(collateral_token, lm_callback, market_amm, market_controller, accounts):
    """
    This unitary test doesn't do trades etc - that has to be done in a full stateful test
    """
    amount = 10 * 10**18
    debt = 5 * 10**18 * 3000
    for i, acc in enumerate(accounts[:10]):
        with boa.env.prank(acc):
            collateral_token._mint_for_testing(acc, amount)
            market_controller.create_loan(amount, debt, 5 + i)

    user_amounts = defaultdict(int)
    for n in range(market_amm.min_band(), market_amm.max_band() + 1):
        cps = lm_callback._debug_collateral_per_share(n)
        for acc in accounts[:10]:
            us = lm_callback._debug_user_shares(acc, n)
            user_amounts[acc] += cps * us // 10**18

    for acc in accounts[:10]:
        assert approx(user_amounts[acc], market_amm.get_sum_xy(acc)[1], 1e-5)
```

**Unit Test 4:**
```python
def test_leverage_property(collateral_token, stablecoin, market_controller, market_amm, fake_leverage, accounts,
                           amount, loan_mul, repay_mul):
    user = accounts[0]

    with boa.env.prank(user):
        collateral_token._mint_for_testing(user, amount)

        debt = int(loan_mul * amount * 3000)
        if (debt // 3000) <= collateral_token.balanceOf(fake_leverage.address) and debt > 0:
            market_controller.create_loan_extended(amount, debt, 5, fake_leverage.address, [0])
        else:
            with boa.reverts():
                market_controller.create_loan_extended(amount, debt, 5, fake_leverage.address, [0])
            return
        assert collateral_token.balanceOf(user) == 0
        expected_collateral = int((1 + loan_mul) * amount)
        assert approx(collateral_token.balanceOf(market_amm.address), expected_collateral, 1e-9, 10)
        xy = market_amm.get_sum_xy(user)
        assert xy[0] == 0
        assert approx(xy[1], expected_collateral, 1e-9, 10)
        assert approx(market_controller.debt(user), debt, 1e-9, 10)
        assert stablecoin.balanceOf(user) == 0

        s0 = stablecoin.balanceOf(market_controller.address)

        if debt * int(repay_mul * 1e18) // 10**18 >= 1:
            market_controller.repay_extended(fake_leverage.address, [int(repay_mul * 1e18)])
        else:
            with boa.reverts():
                market_controller.repay_extended(fake_leverage.address, [int(repay_mul * 1e18)])
            return
        assert market_controller.debt(user) == debt - debt * int(repay_mul * 1e18) // 10**18
        if repay_mul == 1.0:
            assert collateral_token.balanceOf(market_amm.address) == 0
            assert stablecoin.balanceOf(market_amm.address) == 0
            assert market_amm.get_sum_xy(user) == (0, 0)
        assert collateral_token.balanceOf(market_controller.address) == 0
        assert stablecoin.balanceOf(market_controller.address) - s0 == debt * int(repay_mul * 1e18) // 10**18
        if repay_mul == 1.0:
            assert collateral_token.balanceOf(user) == amount
        else:
            assert collateral_token.balanceOf(user) == 0
```

**Unit Test 5:**
```python
def test_price_aggregator(stableswap_a, stableswap_b, stablecoin_a, agg, admin):
    amount = 300_000 * 10**6
    dt = 86400

    assert approx(agg.price(), 10**18, 1e-6)
    assert agg.price_pairs(0)[0].lower() == stableswap_a.address.lower()
    assert agg.price_pairs(1)[0].lower() == stableswap_b.address.lower()

    with boa.env.anchor():
        with boa.env.prank(admin):
            stablecoin_a._mint_for_testing(admin, amount)
            stableswap_a.exchange(0, 1, amount, 0)
            p = stableswap_a.get_p()
            assert p > 10**18 * 1.01

            boa.env.time_travel(dt)

            p_o = stableswap_a.price_oracle()
            assert approx(p_o, p, 1e-4)

            # Two coins => agg price is average of the two
            assert approx(agg.price(), (p_o + 10**18) / 2, 1e-3)
```


# 21304

**Repository:** uber/tchannel-python

**PBT Summary:** A length-prefixed string, when written and then read using `len_prefixed_string` with a specified `len_width`, maintains its original value.

**Total Unit Tests:** 17


**Unit Test 1:**
```python
def test_number_roundtrip(num, width):
    num = num % (2 ** width - 1)
    assert roundtrip(num, rw.number(width)) == num
```

**Unit Test 2:**
```python
def test_len_prefixed_string_roundtrip(s, len_width):
    assume(len(s.encode('utf-8')) <= 2 ** len_width - 1)
    assert roundtrip(s, rw.len_prefixed_string(rw.number(len_width))) == s
```

**Unit Test 3:**
```python
def test_len_prefixed_string_binary_roundtrip(s, len_width):
    assume(len(s) <= 2 ** len_width - 1)
    assert roundtrip(
        s, rw.len_prefixed_string(rw.number(len_width), is_binary=True)
    ) == s
```

**Unit Test 4:**
```python
def test_number(num, width, bs):
    assert rw.number(width).read(bio(bs)) == num
    assert rw.number(width).write(num, BytesIO()).getvalue() == bytearray(bs)
    assert rw.number(width).width() == width
```

**Unit Test 5:**
```python
def test_chain_with_list():
    assert rw.chain(
        [rw.number(1), rw.number(2)]
    ).read(bio([1, 2, 3])) == [1, 515]
```


