import { Routes, Route, Navigate } from "react-router-dom";

import Login from "../pages/Login/Login";
import Dashboard from "../pages/Dashboard/Dashboard";


function RoutesApp(){

    return (

        <Routes>

            <Route 
                path="/"
                element={<Navigate to="/login" />}
            />

            <Route
                path="/login"
                element={<Login />}
            />

            <Route
                path="/dashboard"
                element={<Dashboard />}
            />

        </Routes>

    );

}


export default RoutesApp;