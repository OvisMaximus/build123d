"""

build123d BuildGeneric tests

name: test_build_generic.py
by:   Gumyr
date: July 30th 2022

desc: Unit tests for the build123d build_generic module

license:

    Copyright 2022 Gumyr

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""
import unittest
from math import pi, sqrt
from build123d import *
from build123d import Builder, LocationList


def _assertTupleAlmostEquals(self, expected, actual, places, msg=None):
    """Check Tuples"""
    for i, j in zip(actual, expected):
        self.assertAlmostEqual(i, j, places, msg=msg)


unittest.TestCase.assertTupleAlmostEquals = _assertTupleAlmostEquals


class _TestBuilder(Builder):
    @property
    def _obj(self):
        return self.line

    @property
    def _obj_name(self):
        return "test"

    def __init__(self, mode: Mode = Mode.ADD):
        self.test = "test"
        super().__init__(mode=mode)

    def _add_to_context(self):
        pass

    def _add_to_pending(self):
        pass

    @classmethod
    def _get_context(cls) -> "BuildLine":
        return cls._current.get(None)


class AddTests(unittest.TestCase):
    """Test adding objects"""

    def test_add_to_line(self):
        # Add Edge
        with BuildLine() as test:
            add(Edge.make_line((0, 0, 0), (1, 1, 1)))
        self.assertTupleAlmostEquals((test.wires()[0] @ 1).to_tuple(), (1, 1, 1), 5)
        # Add Wire
        with BuildLine() as wire:
            Polyline((0, 0, 0), (1, 1, 1), (2, 0, 0), (3, 1, 1))
        with BuildLine() as test:
            add(wire.wires()[0])
        self.assertEqual(len(test.line.edges()), 3)

    def test_add_to_sketch(self):
        with BuildSketch() as test:
            add(Face.make_rect(10, 10))
        self.assertAlmostEqual(test.sketch.area, 100, 5)

    def test_add_to_part(self):
        # Add Solid
        with BuildPart() as test:
            add(Solid.make_box(10, 10, 10))
        self.assertAlmostEqual(test.part.volume, 1000, 5)
        with BuildPart() as test:
            add(Solid.make_box(10, 10, 10), rotation=(0, 0, 45))
        self.assertAlmostEqual(test.part.volume, 1000, 5)
        self.assertTupleAlmostEquals(
            (
                test.part.edges()
                .group_by(Axis.Z)[-1]
                .group_by(Axis.X)[-1]
                .sort_by(Axis.Y)[0]
                % 1
            ).to_tuple(),
            (sqrt(2) / 2, sqrt(2) / 2, 0),
            5,
        )

        # Add Compound
        with BuildPart() as test:
            add(
                Compound.make_compound(
                    [
                        Solid.make_box(10, 10, 10),
                        Solid.make_box(5, 5, 5, Plane((20, 20, 20))),
                    ]
                )
            )
        self.assertEqual(test.part.volume, 1125, 5)
        with BuildPart() as test:
            add(Compound.make_compound([Edge.make_line((0, 0), (1, 1))]))
        self.assertEqual(len(test.pending_edges), 1)

        # Add Wire
        with BuildLine() as wire:
            Polyline((0, 0, 0), (1, 1, 1), (2, 0, 0), (3, 1, 1))
        with BuildPart() as test:
            add(wire.wires()[0])
        self.assertEqual(len(test.pending_edges), 3)

    def test_errors(self):
        with self.assertRaises(RuntimeError):
            add(Edge.make_line((0, 0, 0), (1, 1, 1)))

        with BuildPart() as test:
            with self.assertRaises(ValueError):
                add(Box(1, 1, 1), rotation=90)

    def test_unsupported_builder(self):
        with self.assertRaises(RuntimeError):
            with _TestBuilder():
                add(Edge.make_line((0, 0, 0), (1, 1, 1)))

    def test_local_global_locations(self):
        """Check that add is using a local location list"""
        with BuildSketch() as vertwalls:
            Rectangle(40, 90)

        with BuildPart() as mainp:
            with BuildSketch() as main_sk:
                Rectangle(50, 100)
            extrude(amount=10)
            topf = mainp.faces().sort_by(Axis.Z)[-1]
            with BuildSketch(topf):
                add(vertwalls.sketch)
            extrude(amount=15)

        self.assertEqual(len(mainp.solids()), 1)

    def test_multiple_faces(self):
        faces = [
            Face.make_rect(x, x).locate(Location(Vector(x, x))) for x in range(1, 3)
        ]
        with BuildPart(Plane.XY, Plane.YZ) as multiple:
            with Locations((1, 1), (-1, -1)) as locs:
                add(faces)
            self.assertEqual(len(multiple.pending_faces), 16)


class BoundingBoxTests(unittest.TestCase):
    def test_boundingbox_to_sketch(self):
        """Test using bounding box to locate objects"""
        with BuildSketch() as mickey:
            Circle(10)
            with BuildSketch(mode=Mode.PRIVATE) as bb:
                bounding_box(mickey.faces())
                ears = (bb.vertices() > Axis.Y)[:-2]
            with Locations(*ears):
                Circle(7)
        self.assertAlmostEqual(mickey.sketch.area, 586.1521145312807, 5)
        """Test Vertices"""
        with BuildSketch() as test:
            Rectangle(10, 10)
            bounding_box(test.vertices())
        self.assertEqual(len(test.faces()), 1)

    def test_boundingbox_to_part(self):
        with BuildPart() as test:
            Sphere(1)
            bounding_box(test.solids())
        self.assertAlmostEqual(test.part.volume, 8, 5)
        with BuildPart() as test:
            Sphere(1)
            bounding_box(test.vertices())
        self.assertAlmostEqual(test.part.volume, (4 / 3) * pi, 5)

    def test_errors(self):
        with self.assertRaises(ValueError):
            with BuildLine():
                bounding_box()


class ChamferTests(unittest.TestCase):
    def test_part_chamfer(self):
        with BuildPart() as test:
            Box(10, 10, 10)
            chamfer(test.edges(), length=1)
        self.assertLess(test.part.volume, 1000)

    def test_sketch_chamfer(self):
        with BuildSketch() as test:
            Rectangle(10, 10)
            chamfer(test.vertices(), length=1)
        self.assertAlmostEqual(test.sketch.area, 100 - 4 * 0.5, 5)

        with BuildSketch() as test:
            with Locations((-10, 0), (10, 0)):
                Rectangle(10, 10)
            chamfer(
                test.vertices().filter_by_position(Axis.X, minimum=0, maximum=20),
                length=1,
            )
        self.assertAlmostEqual(test.sketch.area, 200 - 4 * 0.5, 5)

    def test_errors(self):
        with self.assertRaises(TypeError):
            with BuildLine():
                chamfer(length=1)

        with self.assertRaises(ValueError):
            with BuildPart() as box:
                Box(1, 1, 1)
                chamfer(box.vertices(), length=1)

        with self.assertRaises(ValueError):
            with BuildSketch() as square:
                Rectangle(1, 1)
                chamfer(square.edges(), length=1)


class FilletTests(unittest.TestCase):
    def test_part_chamfer(self):
        with BuildPart() as test:
            Box(10, 10, 10)
            fillet(test.edges(), radius=1)
        self.assertLess(test.part.volume, 1000)

    def test_sketch_chamfer(self):
        with BuildSketch() as test:
            Rectangle(10, 10)
            fillet(test.vertices(), radius=1)
        self.assertAlmostEqual(test.sketch.area, 100 - 4 + pi, 5)

        with BuildSketch() as test:
            with Locations((-10, 0), (10, 0)):
                Rectangle(10, 10)
            fillet(
                test.vertices().filter_by_position(Axis.X, minimum=0, maximum=20),
                radius=1,
            )
        self.assertAlmostEqual(test.sketch.area, 200 - 4 + pi, 5)

    def test_errors(self):
        with self.assertRaises(TypeError):
            with BuildLine():
                fillet(radius=1)

        with self.assertRaises(ValueError):
            with BuildPart() as box:
                Box(1, 1, 1)
                fillet(box.vertices(), radius=1)

        with self.assertRaises(ValueError):
            with BuildSketch() as square:
                Rectangle(1, 1)
                fillet(square.edges(), radius=1)


class HexArrayTests(unittest.TestCase):
    def test_hexarray_in_sketch(self):
        with BuildSketch() as test:
            Rectangle(70, 70)
            with HexLocations(7, 4, 3, align=(Align.CENTER, Align.CENTER)):
                Circle(5, mode=Mode.SUBTRACT)
        self.assertAlmostEqual(test.sketch.area, 70**2 - 12 * 25 * pi, 5)

    def test_error(self):
        with self.assertRaises(ValueError):
            with BuildSketch():
                with HexLocations(20, 0, 3, align=(Align.CENTER, Align.CENTER)):
                    pass
            with BuildSketch():
                with HexLocations(20, 1, -3, align=(Align.CENTER, Align.CENTER)):
                    pass


class LocationsTests(unittest.TestCase):
    def test_push_locations(self):
        with BuildPart():
            with Locations(Location(Vector())):
                self.assertTupleAlmostEquals(
                    LocationList._get_context().locations[0].to_tuple()[0], (0, 0, 0), 5
                )

    def test_errors(self):
        with self.assertRaises(ValueError):
            with BuildPart():
                with Locations(Edge.make_line((1, 0), (2, 0))):
                    pass


class MirrorTests(unittest.TestCase):
    def test_mirror_line(self):
        edge = Edge.make_line((1, 0, 0), (2, 0, 0))
        wire = Wire.make_circle(1, Plane((5, 0, 0)))
        with BuildLine() as test:
            mirror([edge, wire], Plane.YZ)
        self.assertEqual(
            len(test.edges().filter_by_position(Axis.X, minimum=0, maximum=10)), 0
        )
        self.assertEqual(
            len(test.edges().filter_by_position(Axis.X, minimum=-10, maximum=0)), 2
        )
        with BuildLine() as test:
            Line((1, 0), (2, 0))
            mirror(about=Plane.YZ)
        self.assertEqual(len(test.edges()), 2)

    def test_mirror_sketch(self):
        edge = Edge.make_line((1, 0), (2, 0))
        wire = Wire.make_circle(1, Plane((5, 0, 0)))
        face = Face.make_rect(2, 2, Plane((8, 0)))
        compound = Compound.make_compound(
            [
                Face.make_rect(2, 2, Plane((8, 8))),
                Face.make_rect(2, 2, Plane((8, -8))),
            ]
        )
        with BuildSketch() as test:
            mirror([edge, wire, face, compound], Plane.YZ)
        self.assertEqual(
            len(test.pending_edges.filter_by_position(Axis.X, minimum=0, maximum=10)), 0
        )
        self.assertEqual(
            len(test.faces().filter_by_position(Axis.X, minimum=0, maximum=10)), 0
        )
        self.assertEqual(
            len(test.pending_edges.filter_by_position(Axis.X, minimum=-10, maximum=0)),
            2,
        )
        self.assertEqual(
            len(test.faces().filter_by_position(Axis.X, minimum=-10, maximum=0)), 3
        )

    def test_mirror_part(self):
        cone = Solid.make_cone(2, 1, 2, Plane((5, 4, 0)))
        with BuildPart() as test:
            mirror(cone, Plane.YZ)
        self.assertEqual(
            len(test.solids().filter_by_position(Axis.X, minimum=-10, maximum=0)), 1
        )

    def test_changing_object_type(self):
        """Using gp_GTrsf for the mirror operation may change the nature of the object"""
        ring_r, ring_t = 9, 2
        wheel_r, wheel_t = 10, 6

        with BuildPart() as p:
            with BuildSketch(Plane.XZ) as side:
                Trapezoid(wheel_r, wheel_t / 2, 90, 45, align=(Align.MIN, Align.MIN))
                with Locations((ring_r, ring_t / 2)):
                    Circle(
                        ring_t / 2,
                        align=(Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                    )
                with Locations((wheel_r, ring_t / 2)):
                    Rectangle(
                        2, 2, align=(Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT
                    )
            revolve(axis=Axis.Z)
            mirror(about=Plane.XY)
            construction_face = p.faces().sort_by(Axis.Z)[0]
            self.assertEqual(construction_face.geom_type(), "PLANE")


class OffsetTests(unittest.TestCase):
    def test_single_line_offset(self):
        with BuildLine() as test:
            Line((0, 0), (1, 0))
            offset(amount=1)
        self.assertAlmostEqual(test.wires()[0].length, 2 + 2 * pi, 5)

    def test_line_offset(self):
        with BuildSketch() as test:
            with BuildLine():
                l = Line((0, 0), (1, 0))
                Line(l @ 1, (1, 1))
                offset(amount=1)
            make_face()
        self.assertAlmostEqual(test.sketch.area, pi * 1.25 + 3, 5)

    def test_line_offset(self):
        with BuildSketch() as test:
            with BuildLine() as line:
                l = Line((0, 0), (1, 0))
                Line(l @ 1, (1, 1))
                offset(line.line.edges(), 1)
            make_face()
        self.assertAlmostEqual(test.sketch.area, pi * 1.25 + 3, 5)

    def test_face_offset(self):
        with BuildSketch() as test:
            Rectangle(1, 1)
            offset(amount=1, kind=Kind.INTERSECTION)
        self.assertAlmostEqual(test.sketch.area, 9, 5)

    def test_box_offset(self):
        with BuildPart() as test:
            Box(10, 10, 10)
            offset(amount=-1, kind=Kind.INTERSECTION, mode=Mode.SUBTRACT)
        self.assertAlmostEqual(test.part.volume, 10**3 - 8**3, 5)

    def test_box_offset_with_opening(self):
        with BuildPart() as test:
            Box(10, 10, 10)
            offset(
                amount=-1,
                openings=test.faces() >> Axis.Z,
                kind=Kind.INTERSECTION,
            )
        self.assertAlmostEqual(test.part.volume, 10**3 - 8**2 * 9, 5)

        with BuildPart() as test:
            Box(10, 10, 10)
            offset(
                amount=-1,
                openings=test.faces().sort_by(Axis.Z)[-1],
                kind=Kind.INTERSECTION,
            )
        self.assertAlmostEqual(test.part.volume, 10**3 - 8**2 * 9, 5)

    def test_box_offset_combinations(self):
        with BuildPart() as o1:
            Box(4, 4, 4)
            offset(amount=-1, kind=Kind.INTERSECTION, mode=Mode.REPLACE)
            self.assertAlmostEqual(o1.part.volume, 2**3, 5)

        with BuildPart() as o2:
            Box(4, 4, 4)
            offset(amount=1, kind=Kind.INTERSECTION, mode=Mode.REPLACE)
            self.assertAlmostEqual(o2.part.volume, 6**3, 5)

        with BuildPart() as o3:
            Box(4, 4, 4)
            offset(amount=-1, kind=Kind.INTERSECTION, mode=Mode.SUBTRACT)
            self.assertAlmostEqual(o3.part.volume, 4**3 - 2**3, 5)

        with BuildPart() as o4:
            Box(4, 4, 4)
            offset(amount=1, kind=Kind.INTERSECTION, mode=Mode.ADD)
            self.assertAlmostEqual(o4.part.volume, 6**3, 5)

        with BuildPart() as o5:
            Box(4, 4, 4)
            offset(amount=-1, kind=Kind.INTERSECTION, mode=Mode.ADD)
            self.assertAlmostEqual(o5.part.volume, 4**3, 5)

        with BuildPart() as o6:
            Box(4, 4, 4)
            offset(amount=1, kind=Kind.INTERSECTION, mode=Mode.SUBTRACT)
            self.assertAlmostEqual(o6.part.volume, 0, 5)


class PolarLocationsTests(unittest.TestCase):
    def test_errors(self):
        with self.assertRaises(ValueError):
            with BuildPart():
                with PolarLocations(10, 0, 360, 0):
                    pass


class ProjectionTests(unittest.TestCase):
    def test_project_to_sketch1(self):
        with BuildPart() as loaf_s:
            with BuildSketch(Plane.YZ) as profile:
                Rectangle(10, 15)
                fillet(profile.vertices().group_by(Axis.Y)[-1], 2)
            extrude(amount=15, both=True)
            ref_s_pnts = loaf_s.vertices().group_by(Axis.X)[-1].group_by(Axis.Z)[0]
            origin = (ref_s_pnts[0].to_vector() + ref_s_pnts[1].to_vector()) / 2
            x_dir = ref_s_pnts.sort_by(Axis.Y)[-1] - ref_s_pnts.sort_by(Axis.Y)[0]
            workplane_s = project_workplane(origin, x_dir, (1, 0, 1), 30)
            with BuildSketch(workplane_s) as projection_s:
                project(loaf_s.part.faces().sort_by(Axis.X)[-1])

        self.assertAlmostEqual(projection_s.sketch.area, 104.85204601097809, 5)
        self.assertEqual(len(projection_s.edges()), 6)

    def test_project_to_sketch2(self):
        with BuildPart() as test2:
            Box(4, 4, 1)
            with BuildSketch() as c:
                Rectangle(1, 1)
            project()
            extrude(amount=1)
        self.assertAlmostEqual(test2.part.volume, 4 * 4 * 1 + 1 * 1 * 1, 5)

    def test_project_errors(self):
        with self.assertRaises(ValueError):
            project(workplane=Plane.XY, target=Box(1, 1, 1))

        with self.assertRaises(ValueError):
            project(
                Box(1, 1, 1).vertices().group_by(Axis.Z),
                workplane=Plane.XY,
                target=Box(1, 1, 1),
            )
        with self.assertRaises(ValueError):
            project(
                Box(1, 1, 1).vertices().group_by(Axis.Z),
                target=Box(1, 1, 1),
            )


class RectangularArrayTests(unittest.TestCase):
    def test_errors(self):
        with self.assertRaises(ValueError):
            with BuildPart():
                with GridLocations(5, 5, 0, 1):
                    pass


class ScaleTests(unittest.TestCase):
    def test_line(self):
        with BuildLine() as test:
            Line((0, 0), (1, 0))
            scale(by=2, mode=Mode.REPLACE)
        self.assertAlmostEqual(test.edges()[0].length, 2.0, 5)

    def test_sketch(self):
        with BuildSketch() as test:
            Rectangle(1, 1)
            scale(by=2, mode=Mode.REPLACE)
        self.assertAlmostEqual(test.sketch.area, 4.0, 5)

    def test_part(self):
        with BuildPart() as test:
            Box(1, 1, 1)
            scale(by=(2, 2, 2), mode=Mode.REPLACE)
        self.assertAlmostEqual(test.part.volume, 8.0, 5)

    def test_external_object(self):
        line = Edge.make_line((0, 0), (1, 0))
        with BuildLine() as test:
            scale(line, 2)
        self.assertAlmostEqual(test.edges()[0].length, 2.0, 5)

    def test_error_checking(self):
        with self.assertRaises(ValueError):
            with BuildPart():
                Box(1, 1, 1)
                scale(by="a")


if __name__ == "__main__":
    unittest.main()
