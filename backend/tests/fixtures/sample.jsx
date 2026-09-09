import React from "react";

// A functional component - the most common pattern we'll see in real repos
function Greeting({ name }) {
  return (
    <div className="greeting">
      <h1>Hello, {name}!</h1>
    </div>
  );
}

// A class-based component, less common now but still valid
class Counter extends React.Component {
  render() {
    return <button onClick={this.props.onClick}>Count: {this.props.count}</button>;
  }
}

export default Greeting;

// An arrow-function component - very common in modern React,
// especially with functional/hooks-based code
const Farewell = ({ name }) => {
  return (
    <div className="farewell">
      <p>Goodbye, {name}!</p>
    </div>
  );
};

export { Farewell };