-- 1. Creación de la Base de Datos con una sola 't'
CREATE DATABASE smartech_db;

-- ⚠️ NOTA: Conéctate a 'smartech_db' en pgAdmin antes de ejecutar lo que sigue:

-- 2. Creación de la Tabla de Procesadores
CREATE TABLE procesadores (
    id SERIAL PRIMARY KEY,
    modelo VARCHAR(100) NOT NULL,
    socket VARCHAR(50) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL
);

-- 3. Creación de la Tabla de Placas Madre
CREATE TABLE placas_madre (
    id SERIAL PRIMARY KEY,
    modelo VARCHAR(100) NOT NULL,
    socket VARCHAR(50) NOT NULL,
    ram_soportada VARCHAR(50),
    precio DECIMAL(10, 2) NOT NULL
);

-- 4. Inserción de Datos Base
INSERT INTO procesadores (modelo, socket, precio) VALUES 
('AMD Ryzen 5 5600X', 'AM4', 700.00),
('Intel Core i5 12400F', 'LGA1700', 750.00);

INSERT INTO placas_madre (modelo, socket, ram_soportada, precio) VALUES 
('ASUS B550M-A', 'AM4', 'DDR4', 450.00),
('MSI PRO B660M-A', 'LGA1700', 'DDR4', 550.00);