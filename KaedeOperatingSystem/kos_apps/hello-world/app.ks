// Advanced KScript application demonstrating language features
class Vector {
    private float x;
    private float y;
    private float z;

    public Vector(float x, float y, float z) {
        this.x = x;
        this.y = y;
        this.z = z;
    }

    public float magnitude() {
        return Math.sqrt(x * x + y * y + z * z);
    }

    public Vector add(Vector other) {
        return new Vector(
            this.x + other.x,
            this.y + other.y,
            this.z + other.z
        );
    }

    public string toString() {
        return "Vector(" + x + ", " + y + ", " + z + ")";
    }
}

class VectorCalculator {
    private List<Vector> vectors;

    public VectorCalculator() {
        vectors = new List<Vector>();
    }

    public void addVector(Vector v) {
        vectors.append(v);
    }

    public Vector calculateSum() {
        Vector sum = new Vector(0, 0, 0);
        for (Vector v in vectors) {
            sum = sum.add(v);
        }
        return sum;
    }
}

function main() {
    // Create a vector calculator
    VectorCalculator calc = new VectorCalculator();

    // Add some vectors
    calc.addVector(new Vector(1, 0, 0));
    calc.addVector(new Vector(0, 1, 0));
    calc.addVector(new Vector(0, 0, 1));

    // Calculate and print sum
    Vector sum = calc.calculateSum();
    IO.print("Sum of vectors: " + sum.toString());
    IO.print("Magnitude: " + sum.magnitude());
}

main();