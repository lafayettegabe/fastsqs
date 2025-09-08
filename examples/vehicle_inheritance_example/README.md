# Vehicle Inheritance Routing Example

This example demonstrates how to use **class inheritance** with SQSRouter to create a base event class and specific subclasses that share common parameters but add their own specialized fields.

## Architecture

```
Vehicle (Base Class)
├── vehicle_id: str
├── location: str  
└── timestamp: str (optional)

├── Car (inherits Vehicle)
│   ├── fuel_level: float
│   ├── mileage: int
│   └── engine_type: Literal["gasoline", "diesel", "hybrid", "electric"]
│
├── Bus (inherits Vehicle)
│   ├── passenger_count: int
│   ├── route_number: str
│   ├── capacity: int
│   └── accessibility_enabled: bool
│
├── Truck (inherits Vehicle)
│   ├── cargo_weight: float
│   ├── cargo_type: str
│   ├── max_weight: float
│   └── trailer_attached: bool
│
└── Motorcycle (inherits Vehicle)
    ├── engine_cc: int
    ├── license_type: Literal["A", "A1", "A2"]
    └── helmet_detected: bool
```

## Key Features

1. **Base Class**: `Vehicle` provides common fields (`vehicle_id`, `location`, `timestamp`)
2. **Specialized Subclasses**: Each vehicle type adds specific fields and validation
3. **Type Safety**: Full pydantic validation for each vehicle type
4. **Polymorphic Routing**: Same router handles all vehicle types based on `type` field
5. **Business Logic**: Each handler can implement vehicle-specific business rules

## Message Examples

### Car Message
```json
{
  "type": "car",
  "vehicle_id": "CAR-001",
  "location": "Downtown Parking",
  "fuel_level": 0.75,
  "mileage": 45000,
  "engine_type": "hybrid"
}
```

### Bus Message
```json
{
  "type": "bus",
  "vehicle_id": "BUS-101",
  "location": "Central Station",
  "passenger_count": 35,
  "route_number": "Route 42",
  "capacity": 60,
  "accessibility_enabled": true
}
```

### Truck Message
```json
{
  "type": "truck",
  "vehicle_id": "TRUCK-501",
  "location": "Loading Dock",
  "cargo_weight": 35.5,
  "cargo_type": "Electronics",
  "max_weight": 40.0,
  "trailer_attached": true
}
```

## Benefits

1. **Code Reuse**: Common vehicle properties defined once in base class
2. **Type Safety**: Each vehicle type has specific validation rules
3. **Extensibility**: Easy to add new vehicle types by inheriting from `Vehicle`
4. **Business Logic**: Each handler can implement vehicle-specific rules (e.g., overweight detection)
5. **Maintainability**: Changes to common fields only need to be made in the base class

## Usage

```bash
# Run the example
python lambda_function.py
```

## Expected Output

You'll see different handlers processing each vehicle type with their specific business logic:

- `[CAR]` - Fuel level, mileage, engine type information
- `[BUS]` - Passenger occupancy, route information, accessibility status
- `[TRUCK]` - Cargo weight, overweight detection, trailer status
- `[MOTORCYCLE]` - Engine size, license requirements, safety compliance
- `[VEHICLE]` - Generic vehicle information for unknown types
