import React from "react";

interface GreetingProps {
  name: string;
}

// A typed functional component - the standard modern TSX pattern
function Greeting({ name }: GreetingProps): JSX.Element {
  return (
    <div className="greeting">
      <h1>Hello, {name}!</h1>
    </div>
  );
}

// A typed arrow-function component
const Farewell = ({ name }: GreetingProps): JSX.Element => {
  return (
    <div className="farewell">
      <p>Goodbye, {name}!</p>
    </div>
  );
};

export { Greeting, Farewell };